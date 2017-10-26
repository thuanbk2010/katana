import json
import time
from collections import defaultdict

from twisted.application import service
from twisted.internet import reactor
from twisted.python import log
import sqlalchemy as sa

from buildbot import config
from buildbot.util.lru import LRUCache


class BuildRequestMerger(config.ReconfigurableServiceMixin, service.Service):
    """
    Wrapper around buildsets.addBuildset that does merging before
    buildrequests hit the db.

    This will only do merges within a same buildchain, and will never merge
    the top level build.
    """

    # Basic list of properties that must match for a buildrequest to be merged
    # BuilderConfigs can define additional properties (see _propertiesMatch)
    BASE_MERGE_PROPERTIES = ['force_rebuild', 'force_chain_rebuild']

    def __init__(self, master):
        self.master = master
        self.startbrid_cache = LRUCache(
            miss_fn=self.__startbridCacheMissFn, max_size=20000)
        self.properties_cache = LRUCache(
            miss_fn=None,  # Cache contents are handled manually
            max_size=20000)

    def addBuildset(self,
                    sourcestampsetid,
                    reason,
                    properties,
                    triggeredbybrid=None,
                    builderNames=None,
                    external_idstring=None,
                    _reactor=reactor):
        """
        ..seealso:: buildsets.addBuildset
            For parameter details
        """
        start = time.time()

        buildsetLog = {
            'name': 'addBuildset',
            'description':
            'Log merges within a chain while adding new buildsets',
            'sourcestampsetid': sourcestampsetid,
            'builderNames': builderNames,
        }

        # For every builderName in this buildset, check which ones can be merged
        breqsToMerge = {}
        for builderName in builderNames:
            builderMergeStart = time.time()

            if triggeredbybrid is None:
                # This is a top level build, so it cannot be merged
                mergeBrid = None
            else:
                # If we are not the top level build, find this chain's top level build
                startbrid = self.startbrid_cache.get(triggeredbybrid)

                # And look for a builder that matches the configured properties
                mergeProperties = self.master.botmaster.builders[
                    builderName].config.mergeProperties
                mergeBrid = self._getMergeBrid(startbrid, builderName,
                                               properties, mergeProperties)

                # If we found one, add it to our merge map
                if mergeBrid:
                    breqsToMerge[builderName] = mergeBrid

            buildsetLog[builderName] = {
                'elapsed': time.time() - builderMergeStart,
                'mergeBrid': mergeBrid
            }

        buildsetLog['elapsed'] = time.time() - start

        log.msg(json.dumps(buildsetLog))

        return self.master.db.buildsets.addBuildset(
            sourcestampsetid=sourcestampsetid,
            reason=reason,
            properties=properties,
            triggeredbybrid=triggeredbybrid,
            builderNames=builderNames,
            breqsToMerge=breqsToMerge,
            external_idstring=external_idstring,
            _reactor=_reactor, )

    def _getMergeBrid(self, startbrid, builderName, properties,
                      mergeProperties):
        """
        :param str startbrid:
        :param str builderName:
        :param dict(str,str) properties:
        :param list(str) mergeProperties:

        :return str or None:
            Build request id for a request that can be merged into (matches
            buiderName, properties and sourcestamp information).

            `None` if no match was found.
        """
        # Never merge if a build request has a selected_slave
        # This might happen when a user wants to test the same build in different
        # slaves to look for instabilities
        if 'selected_slave' in properties:
            return None

        # Get an initial list of all breqs of the same name, in the same chain
        matchingBreqs = self._getSameBuildersInChain(startbrid, builderName)

        # Get properties for matching breqs (done in a single queyr for optimization)
        otherProperties = self._getBuildsetsProperties(
            [bsid for bsid, _brid in matchingBreqs])

        # Check if relevant properties match
        for otherBuildsetid, otherBrid in matchingBreqs:
            if self._propertiesMatch(properties,
                                     otherProperties[otherBuildsetid],
                                     mergeProperties):

                # If they match, merge against this buildrequest
                return otherBrid

        # If we can't find any match, return None
        return None

    def _getSameBuildersInChain(self, startbrid, builderName):
        """
        :param str startbrid:
        :param str builderName:
        :return tuple(str,str):
            (buildsetid, brid) for all buildrequests in the same chain (`startbrid`)
            with the same `builderName`
        """
        breq_tbl = self.master.db.model.buildrequests

        def __getSameBuildersInChain(conn):
            # Select buildrequests `buildsetit` and `brid`
            # q = sa.select(breq_tbl.c.buildsetid, breq_tbl.c.id) \

            # For builders in the same chain
            #     .where(breq_tbl.c.startbrid == startbrid) \

            # With the same name
            #     .where(breq_tbl.c.buildername == builderName) \

            # That were not merged themselves (only merge against one / main target)
            #     .where(breq_tbl.c.mergebrid == None) \
            q = sa.select(breq_tbl.c.buildsetid, breq_tbl.c.id) \
                .where(breq_tbl.c.startbrid == startbrid) \
                .where(breq_tbl.c.buildername == builderName) \
                .where(breq_tbl.c.mergebrid == None)
            res = conn.execute(q)
            return res.fetchall() or []

        return self.master.db.pool.do(__getSameBuildersInChain)

    def _propertiesMatch(self, properties, otherProperties, mergeProperties):
        """
        :param dict(str,str) properties:
        :param dict(str,str) otherProperties:
        :param list(str) mergeProperties:
            List of properties that must match
        :return bool:
            True if `properties` and `otherProperties` match for a list of
            `mergeProperties` to be checked
        """
        if 'selected_slave' in otherProperties:
            return False

        for propertyName in self.BASE_MERGE_PROPERTIES + mergeProperties:
            if properties.get(propertyName, None) != otherProperties.get(
                    propertyName, None):
                return False

        return True

    def _getBuildsetsProperties(self, buildsetids):
        properties = {}

        # Fill in properties from cache
        for buildsetid in buildsetids:
            if buildsetid in self.properties_cache.cache:
                properties[buildsetid] = self.properties_cache.get(buildsetid)

        # Read missing properties in a single query
        missing_buildsetids = set(buildsetids).difference(properties.keys())
        if missing_buildsetids:
            prop_tbl = self.master.db.model.buildset_properties

            def __getBuildsetsProperties(conn):
                q = sa.select(prop_tbl.c.buildsetid, prop_tbl.c.property_name, prop_tbl.c.property_value) \
                    .where(prop_tbl.c.buildsetid.in_(missing_buildsetids))
                res = conn.execute(q)

                missing_properties = {
                    buildsetid: {}
                    for buildsetid in missing_buildsetids
                }
                for (buildsetid, property_name, property_value) in (
                        res.fetchall() or []):
                    missing_properties[buildsetid][
                        property_name] = property_value

                # Return properties
                return missing_properties

            properties.update(self.master.db.pool.do(__getBuildsetsProperties))

        # Populate cache with new values
        for buildsetid in missing_buildsetids:
            self.properties_cache.put_new(buildsetid, properties[buildsetid])

        return properties

    def __startbridCacheMissFn(self, brid):
        """
        Given a build request id `brid`, find the top level build that started
        the chain containing it.

        :param str brid:
        :return str:
            Build request id
        """
        breq_tbl = self.master.db.model.buildrequests

        def __getStartbrid(conn):
            q = sa.select(breq_tbl.c.startbrid) \
                .where(breq_tbl.c.id == brid)

            startbrid = conn.execute(q).fetchone().startbrid

            # If startbrid is None, then `brid` IS the chain's top level build
            return startbrid or brid

        return self.master.db.pool.do(__getStartbrid)

import json
import time

from twisted.application import service
from twisted.internet import reactor
from twisted.python import log

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
            miss_fn=self.master.db.buildrequests.getTopLevelChainBrid,
            max_size=20000)
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
        matchingBreqs = self.master.db.buildrequests.getMergeTargetsInChain(
            startbrid, builderName)

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
            properties.update(
                self.master.db.buildsets.getBuildsetsProperties(
                    missing_buildsetids))

        # Populate cache with new values
        for buildsetid in missing_buildsetids:
            self.properties_cache.put_new(buildsetid, properties[buildsetid])

        return properties

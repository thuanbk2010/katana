import json
import time

from twisted.application import service
from twisted.internet import reactor
from twisted.python import log
import sqlalchemy as sa

from buildbot import config
from buildbot.process.buildrequest import Priority
from buildbot.util.lru import LRUCache


class BuildRequestMerger(config.ReconfigurableServiceMixin, service.Service):
    # Basic list of properties that must match for a buildrequest to be merged
    # BuilderConfigs can define additional properties (see _propertiesMatch)
    BASE_MERGE_PROPERTIES = ['force_rebuild', 'force_chain_rebuild']

    def __init__(self, master):
        self.master = master
        self.properties_cache = LRUCache(
            miss_fn=self.__propertiesCacheMissFn, max_size=20000)

    def addBuildset(self,
                    sourcestampsetid,
                    reason,
                    properties,
                    triggeredbybrid=None,
                    builderNames=None,
                    external_idstring=None,
                    _reactor=reactor):
        """
        Wrapper around buildsets.addBuildset that does merging before
        buildrequests hit the db

        ..seealso:: buildsets.addBuildset
        """
        start = time.time()

        buildsetLog = {
            'name': 'addBuildset',
            'description': 'Log merges done while adding new buildsets',
            'sourcestampsetid': sourcestampsetid,
            'builderNames': builderNames,
        }

        codebase, branch, revision = self._getSourceStampInfo(sourcestampsetid)

        buildsetLog['_getSourceStampInfo'] = {
            'elapsed': time.time() - start,
            'codebase': codebase,
            'branch': branch,
            'revision': revision,
        }

        # Find the priority for this buildset
        priority = Priority.Default
        if 'priority' in properties:
            priority_property = properties.get('priority')[0]
            priority = priority_property if priority_property and int(
                priority_property) > 0 else Priority.Default

        # For every builderName in this buildset, check which ones can be merged
        breqsToMerge = {}
        for builderName in builderNames:
            builderMergeStart = time.time()
            mergeBrid = self._getMergeBrid(
                self.master.botmaster.builders[builderName], builderName,
                priority, codebase, branch, revision, properties)
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

    def _getSourceStampInfo(self, sourcestampsetid):
        """
        :param str sourcestampsetid:
        :return tuple(str,str,str):
            (codebase, branch, revision) for the given `sourcestampsetid`
        """
        ss_tbl = self.master.db.model.sourcestamps

        def __getSourcestampInfo(conn):
            res = conn.execute(
                sa.select([
                    ss_tbl.c.branch,
                    ss_tbl.c.revision,
                    ss_tbl.c.repository,
                    ss_tbl.c.codebase,
                ]).where(ss_tbl.c.sourcestampsetid == sourcestampsetid))

            row = res.fetchone()
            return row.codebase, row.branch, row.revision

        return self.master.db.pool.do(__getSourcestampInfo)

    def _getMergeBrid(self, builder, builderName, priority, codebase, branch,
                      revision, properties):
        """
        :param Builder builder:
        :param str builderName:
        :param str codebase:
        :param int priority:
        :param str branch:
        :param str revision:
        :param dict(str,str) properties:

        :return str or None:
            Build request id for a request that can be merged into (matches
            buiderName, properties and sourcestamp information).

            `None` if no match was found.
        """
        if 'selected_slave' in properties:
            return None

        # Get an initial list of all breqs that match the given source stamp data
        matchingBrids = self._getBuildRequestIdsMatchingSourceStamp(
            builderName, priority, codebase, branch, revision)

        # Check if relevant properties match
        for otherBuildsetid, otherBrid in matchingBrids:
            otherProperties = self.properties_cache.get(otherBuildsetid)
            if self._propertiesMatch(properties, otherProperties,
                                     builder.config.mergeProperties):
                return otherBrid
        return None

    def _getBuildRequestIdsMatchingSourceStamp(self, builderName, priority,
                                               codebase, branch, revision):
        """
        :param str builderName:
        :param int priority:
        :param str codebase:
        :param str branch:
        :param str revision:
        :return tuple(str,str):
            (buildsetid, brid) for all buildrequests that match the given
            builderName, priority and sourceStamp information.

            Note that builds started without a revision (only a branch) might
            not be able to merge to previous builds that were also started
            without a revision but have already started and found the latest
            revision in that branch. This happens because in this case we will
            be searching for other buildRequests that have `revision==None`,
            and running builds at some point update their properties to a real
            revision.
        """
        bs_tbl = self.master.db.model.buildsets
        breq_tbl = self.master.db.model.buildrequests
        ss_tbl = self.master.db.model.sourcestamps

        def __getBuildRequestIdsMatchingSourcestamp(conn):
            # Select buildrequests
            # q = sa.select(breq_tbl.c.buildsetid, breq_tbl.c.id) \

            # That are not complete
            #     .where(breq_tbl.c.complete == 0) \

            # For this same builder
            #     .where(breq_tbl.c.buildername == builderName) \

            # That were not merged themselves (only merge against one / main target)
            #     .where(breq_tbl.c.mergebrid == None) \

            # And has the same priority (we could be smarter here, but it would make the query
            # more complicated and possibly invert the merge target)
            #     .where(breq_tbl.c.priority == priority) \

            # Join on same sourcestamp (codebase, branch, revision)
            #     .join(bs_tbl, bs_tbl.c.id == breq_tbl.c.buildsetid) \
            #     .join(ss_tbl, ss_tbl.c.sourcestampsetid == bs_tbl.c.sourcestampsetid) \
            #     .where(
            #         ss_tbl.c.codebase == codebase,
            #         ss_tbl.c.branch == branch,
            #         ss_tbl.c.revision == revision,
            #     )
            q = sa.select(breq_tbl.c.buildsetid, breq_tbl.c.id) \
                .where(breq_tbl.c.complete == 0) \
                .where(breq_tbl.c.buildername == builderName) \
                .where(breq_tbl.c.mergebrid == None) \
                .where(breq_tbl.c.priority == priority) \
                .join(bs_tbl, bs_tbl.c.id == breq_tbl.c.buildsetid) \
                .join(ss_tbl, ss_tbl.c.sourcestampsetid == bs_tbl.c.sourcestampsetid) \
                .where(
                    ss_tbl.c.codebase == codebase,
                    ss_tbl.c.branch == branch,
                    ss_tbl.c.revision == revision,
                )
            res = conn.execute(q)
            return res.fetchall() or []

        return self.master.db.pool.do(__getBuildRequestIdsMatchingSourcestamp)

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

    def __propertiesCacheMissFn(self, buildsetid):
        """
        :param str buildsetid:
        :return dict(str,str):
            Dictionary of properties for the given `buildsetid`
        """
        prop_tbl = self.master.db.model.buildset_properties

        def __getBuildRequestProperties(conn):
            q = sa.select(prop_tbl.c.property_name, prop_tbl.c.property_value) \
                .where(prop_tbl.c.buildsetid == buildsetid)
            res = conn.execute(q)

            # Return properties as a dictionary
            return {k: v for (k, v) in (res.fetchall() or [])}

        return self.master.db.pool.do(__getBuildRequestProperties)
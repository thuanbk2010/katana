from twisted.internet import defer

from buildbot.status.web.base import HtmlResource


class MybuildsResource(HtmlResource):
    pageTitle = "MyBuilds"

    @defer.inlineCallbacks
    def content(self, req, cxt):
        master = self.getBuildmaster(req)
        username = cxt['authz'].getUsernameFull(req)
        builds = yield master.db.builds.getLastBuildsOwnedBy(username, master.status.botmaster)

        cxt['builds'] = builds
        template = req.site.buildbot_service.templates.get_template("mybuilds.html")
        template.autoescape = True
        defer.returnValue(template.render(**cxt))

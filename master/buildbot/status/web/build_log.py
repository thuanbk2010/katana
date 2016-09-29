import urllib
from buildbot.status.web.base import HtmlResource, path_to_builder, \
    path_to_build, css_classes, \
    path_to_codebases, path_to_builders, path_to_step


class BuildLogResource(HtmlResource):

    def __init__(self, build_status):
        HtmlResource.__init__(self)
        self.build_status = build_status

    def getPageTitle(self, request):
        return ("Katana - %s Build #%d Log" %
                (self.build_status.getBuilder().getFriendlyName(),
                 self.build_status.getNumber()))

    def content(self, req, cxt):
        b = self.build_status

        req.setHeader('Cache-Control', 'no-cache')

        builder = self.build_status.getBuilder()
        cxt['builder'] = builder
        cxt['builder_name'] = builder.getFriendlyName()
        cxt['build_number'] = b.getNumber()
        cxt['builder_name_link'] = urllib.quote(self.build_status.getBuilder().getName(), safe='')
        cxt['b'] = b
        project = cxt['selectedproject'] = builder.getProject()
        cxt['path_to_builder'] = path_to_builder(req, b.getBuilder())
        cxt['path_to_builders'] = path_to_builders(req, project)
        cxt['path_to_codebases'] = path_to_codebases(req, project)

        template = req.site.buildbot_service.templates.get_template("build_log.html")
        return template.render(**cxt)
import os
from twisted.python import log

def generate_logstash_config(manifest, logsdir, command=None):
    """
    Given a manifest dictionary, generates a logstash configuration file that includes the manifest data as log fields
    @param manifest: A dictionary of the details of the build
    @param command: The command currently being run
    @return: none
    """

    # Example manifest:
    # {
    #     "buildbotURL": "http://localhost:8001/",
    #     "buildNumber": 32,
    #     "builderName": "proj1000-Generate Large Log",
    #     "slaveName": "build-slave-02",
    #     "stepName": "Run excessively long bash command.",
    #     "sourcestamps": [
    #         {
    #             "revision": "",
    #             "revision_short": "",
    #             "hasPatch": false,
    #             "branch": "default",
    #             "changes": [],
    #             "project": "general",
    #             "repository": "http://mercurial-mirror.hq.unity3d.com/path/to/dummy/repo",
    #             "codebase": "dummy",
    #             "totalChanges": 0
    #         }
    #     ],
    #     "reason": "A build was forced by 'barry barry@unity3d.com': ",
    #     "owners": [
    #         "barry barry@unity3d.com"
    #     ]
    # }

    # Mapping: logstash filter field : manifest field
    sourcestamps_headers = {'codebases': 'codebase',
                            'repositoryURLs': 'repository',
                            'branches': 'branch',
                            'revisions': 'revision',
                            }

    sourcestamps_text = ""
    for logstashField, manifestField in sourcestamps_headers.iteritems():
        manifestValues = ['"%s"' % s[manifestField] for s in manifest['sourcestamps']]
        manifestValues = ", ".join(manifestValues)
        sourcestamps_text += '      "sourcestamps_%s" => [%s]\n' % (logstashField, manifestValues)

    config_text = """
input {
    file {
        path =>  [
        "%s/**/*.log",
        "%s/**/*.txt"
        ]
    }
}

filter {
  grok {
      match => { "message" => ".*" }
    add_field => {
      "buildmasterURL" => "%s"
      "builderName" => "%s"
      "buildNumber" => "%s"
      "slaveName" => "%s"
      "stepName" => "%s"
      "command" => "%s"
%s
      "owners" => "%s"
      "reason" => "%s"
      "logfilePath" => "%s"
    }
  }
}
""" % (
        #inputs
        logsdir,
        logsdir,
        #filters
        manifest["buildbotURL"],
        manifest["builderName"],
        manifest["buildNumber"],
        manifest["slaveName"],
        manifest["stepName"],
        command,
        sourcestamps_text.rstrip("\n"),
        manifest["owners"],
        manifest["reason"],
        manifest['logFilePath'],
    )

    try:
        os.stat(manifest["logstashConfDir"])
    except:
        os.makedirs(manifest["logstashConfDir"])
    with open("%s/logstash-katana.conf" % manifest["logstashConfDir"], 'w') as cfg:
        cfg.write(config_text)
    log.msg("Created Logstash configuration file %s." %
            "%s/logstash-katana.conf" % manifest["logstashConfDir"])

    return

import os
import time
from twisted.python import log


class logstashgen():

    previous_manifest = None

    def generate_logstash_config(self, manifest, logsdir):
        """
        Given a manifest dictionary, generates a logstash configuration file that includes the manifest data as log fields
        @param manifest: A dictionary of the details of the build
        @return: none
        """

        # Don't save new file if there's nothing new to save
        if self.previous_manifest:
            excluded_differences = ["sourcestamps", "stepName", "stepNumber", "logFilePath"]
            diffkeys = [k for k in manifest if manifest[k] != self.previous_manifest[k] and k not in excluded_differences]
            if len(diffkeys) == 0:
                log.msg("No manifest changes detected, not writing logstash config.")
                return
            for k in diffkeys:
                #TODO: remove this logging, it's just for testing.
                log.msg("Change in logstash manifest - ", k, ':', self.previous_manifest[k], '->', manifest[k])
        else:
            log.msg("No previous logstash config file created by this slave in this session.")

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
    %s
          "owners" => "%s"
          "reason" => "%s"
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
            sourcestamps_text.rstrip("\n"),
            manifest["owners"],
            manifest["reason"],
        )

        try:
            os.stat(manifest["logstashConfDir"])
        except:
            os.makedirs(manifest["logstashConfDir"])
        with open("%s/logstash-katana.conf" % manifest["logstashConfDir"], 'w') as cfg:
            cfg.write(config_text)
        log.msg("Wrote to Logstash configuration file %s. Waiting 2s for Logstash to reload." %
                "%s/logstash-katana.conf" % manifest["logstashConfDir"])
        time.sleep(2)
        self.previous_manifest = manifest
        return

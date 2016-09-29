/*global define, Handlebars */
define(['elasticsearch', 'trunk8'], function(require) {
  "use strict";
  var searchBox = $('#elastic-search');

  var logContainer = $('.log-container')
  var logContent = $('#log-content');
  var logStatus = $('.log-status');

  var pageNum = 1;
  var perPage = 150;
  var continueHit = false;

  var logPath = "/Users/kateryna/pr/hackweeek/tests/logs/utr_out.txt";

  var esConnection = {
    host: 'localhost:9200',
    log: 'trace'
  };

  var index = 'buildlog'

  var loadingIcon = $('.log-loading-icon');

  var searchQuery2 = {
    index: index,

    from: (pageNum - 1) * perPage,
    size: perPage,
    body: {
      "query": {
        "constant_score": {
          "query": {
            "bool": {
              "must": [
                { "match": { "path": "/Users/kateryna/pr/hackweeek/tests/logs/utr_out.txt" } },
              ],
              "should": [
                { "wildcard": { "message": "*" } }
              ]
            }
          }
        }
      }
    }
  }


  var client;

  var rtLog = {
    init: function() {
      console.log('rtLog init')

      searchBox.on('input', function() {
        var value = this.value.toLowerCase() || "*";
        searchQuery2.body.query.constant_score.query.bool.should[0].wildcard.message = value;
        pageNum = 1;
        searchQuery2.from = (pageNum - 1) * perPage;
        rtLog.getLogPage(pageNum, perPage, searchQuery2, rtLog.renderLog)
      });

      rtLog.connectElasticsearch();

      rtLog.initTagFilter();

      rtLog.getLogPage(pageNum, perPage, searchQuery2, rtLog.renderLog);
      //rtLog.initPagination(pageNum, perPage, searchQuery, rtLog.renderLog)
    },

    initFilters: function() {
      var typeFilter = $('#type-filter');
      var lineFilter = $('#line-filter');
      var tagFilter = $('#tag-filter');
      var fieldFilter = $('#field-filter');

      rtLog.initTagFilter();
    },

    initTagFilter: function() {
      client.indices.getMapping({ index: index }, function(error, response) {
        if (error) {
          console.log(error);
        } else {
          console.log(response);
          var fieldFilter = $('#field-filter');

          var properties = Object.keys(response.buildlog.mappings.logs.properties)
          var items = properties.map(function(value, i) { return { id: i, text: value } })
          fieldFilter.select2({
            data: items,
            placeholder: "Fields",
            allowClear: true,
            multiple: true,
          });
        }
      });
    },

    connectElasticsearch: function() {
      client = new elasticsearch.Client(esConnection);

      if (!client) {
        console.error('Elasticsearch client is undefined.');
        return
      }

      client.ping({
        hello: "elasticsearch"
      }, function(error) {
        if (error) {
          console.error('Elasticsearch cluster is down!');
        } else {
          console.log('Elasticsearch connection successfully.');
        }
      });
    },

    initPagination: function(pageNum, perPage, searchQuery, renderCallback) {
      rtLog.getLogPage(pageNum, perPage, searchQuery, rtLog.renderLog);

      logContainer.scroll(function() {
        if (logContainer.scrollTop() >= $(document).height()) {
          pageNum++;
          rtLog.getLogPage(pageNum, perPage, searchQuery, renderCallback)
        }
      });
    },

    getLogPage: function(pageNum, perPage, searchQuery, renderCallback) {
      loadingIcon.show();
      client.search(searchQuery)
        .then(function(resp) {
          if (pageNum === 1) {
            logContent.empty()
          }
          loadingIcon.hide();

          renderCallback(resp);
        }, function(err) {
          console.trace(err.message);
        });

    },

    renderLog: function(resp) {
      if (!resp) {
        return;
      }
      logStatus.empty()
      logStatus.append('<div><span>Total hits: </span>' + resp.hits.total + '</div>')
      logStatus.append('<div><span>Showed lines from </span>0<span> to </span>' + ((pageNum - 1) * perPage + perPage) + '</div>')

      var fields = resp.hits.hits.map(function(item) {
        return item.fields || item['_source'];
      })

      if (!!fields) {
        fields.forEach(function(value) {
          logContent.append($(rtLog.renderLogLine(value)))
        })
      }
      rtLog.trunkMessages()
    },

    renderLogLine: function(value) {
      var timestamp = moment(value['@timestamp'][0]).format('HH:MM:SS')
      var lineText = value.message
      var lineColor = ""

      if (value.json) {
        lineText = value.json.name
        lineColor = rtLog.getUtrTestColor(value.json.state)
      }
      if (value.error_type) {
        lineColor = rtLog.getLineColor(value.error_type)
      }

      return '<tr class="log-line ' + lineColor + '"><td><span class="log-time">' +
        timestamp + '</span></td><td><span class="log-message">' +
        lineText + '</span></td></tr>'
    },

    renderMessage: function(message) {
      return '<span class="log-message">' + message + '</span>'
    },

    renderJson: function(json) {
      return '<span class="log-message ' + rtLog.getStateColor(json.state) + '">' + json.name + '</span>'
    },

    getValueColor: function(value) {
      if (value.json) {
        return rtLog.getTestColor(value.json.state)
      }
      if (value.error_type) {

      }
    },
    getLineColor: function(error) {
      switch (state) {
        case 'warning':
          return 'log-line-warning';
        case 'failed':
          return 'log-line-failed';
        case 'error':
          return 'log-line-error';
        default:
          return '';
      }
    },

    getUtrTestColor: function(state) {
      switch (state) {
        case 4:
          return 'log-line-passed';
        case 5:
          return 'log-line-failed';
        case 6:
          return 'log-line-error';
        default:
          return '';
      }
    },

    trunkMessages: function() {
      $('.log-message').trunk8({
        fill: '&hellip; <a id="read-more" href="#">more</a>'
      });

      $(document).on('click', '#read-more', function(event) {
        $(this).parent().trunk8('revert').append(' <a id="read-less" href="#">less</a>');
        return false;
      });

      $(document).on('click', '#read-less', function(event) {
        $(this).parent().trunk8();
        return false;
      });
    }
  }

  return rtLog;
})
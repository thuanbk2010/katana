/*global define, Handlebars */
define(function(require) {
  "use strict";

  var es = require('elasticApi')
  var trunk8 = require('trunk8')

  var searchBox = $('#elastic-search');
  var logContainer = $('.log-container')
  var logContent = $('#log-content');
  var logStatus = $('.log-status');
  var warningsFilter = { "match": { "error_type": "warning" } };
  var errorFilter = { "match": { "error_type": "error" } };
  var filters = []

  var instantData = JSON.parse(instantJSON.global.data);
  var connection = {
    host: instantData.elasticUrl || '0.0.0.0:9200',
    log: 'trace'
  };

  var lastHitsCount = 0;

  var loadingIcon = $('.log-loading-icon');

  var settings = {
    index: instantData.elasticIndex || "",
    build: instantJSON.build.number,
    builder: instantJSON.build.builder_name,
    steps: null,
    codebase: null,
    branch: null,
    pageNum: 1,
    perPage: 100
  }

  var rtLog = {
    init: function() {
      es.connect(connection, settings);
      searchBox.on('input', function() {
        logContent.empty();
        es.filterAll(this.value, rtLog.renderLog)
      });

      $("#log-cb-errors").click(function() {
        logContent.empty();
        if ($(this).is(':checked')) {
          filters.push(errorFilter)
          es.filter(filters, rtLog.renderLog)
        } else {
          filters.pop(errorFilter)
          es.clearFilter(errorFilter, rtLog.renderLog)
        }
      });

      $("#log-cb-warnings").click(function() {
        logContent.empty();
        if ($(this).is(':checked')) {
          filters.push(warningsFilter)
          es.filter(filters, rtLog.renderLog)

        } else {
          filters.pop(warningsFilter)
          es.clearFilter(warningsFilter, rtLog.renderLog)
        }


      });

      rtLog.initTagFilter();
      loadingIcon.show();
      rtLog.initPaging();
    },

    initPaging: function() {
      logContent.empty();
      es.getPage(rtLog.renderLog);

      logContainer.scroll(function() {
        if (logContainer.scrollTop() >= $(document).height()) {
          if (settings.sort === "desc") {
            return
          }
          loadingIcon.show();
          es.nextPage(rtLog.renderLog);
        }
      });
    },


    initFilters: function() {
      var typeFilter = $('#type-filter');
      var lineFilter = $('#line-filter');
      var tagFilter = $('#tag-filter');
      var fieldFilter = $('#field-filter');

      rtLog.initTagFilter();
    },

    initTagFilter: function() {
      es.getMapping(function(properties) {
        var properties = Object.keys(properties)
        var items = properties.map(function(value, i) { return { id: i, text: value } })
        $('#field-filter').select2({
          data: items,
          placeholder: "Fields",
          allowClear: true,
          multiple: true,
        });
      })
    },

    renderLog: function(resp) {
      if (!resp) {
        return;
      }

      loadingIcon.hide();
      logStatus.empty()
      logStatus.append('<div><span>Total hits: </span>' + resp.hits.total + '</div>')
      logStatus.append('<div><span>Page size: </span>' + settings.perPage + '</div>')
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

    getLineColor: function(error) {
      switch (error) {
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
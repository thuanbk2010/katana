/*global define, Handlebars */
define(function(require) {
  "use strict";

  var es = require('elasticApi')
  var trunk8 = require('trunk8')

  var searchBox = $('#elastic-search');
  var logContainer = $('.log-container')
  var logContent = $('#log-content');
  var logStatus = $('.log-status');
  var typeProperties = {}

  var instantData = JSON.parse(instantJSON.global.data);
  var connection = {
    host: instantData.elasticUrl || '0.0.0.0:9200'
  };

  var lastHitsCount = 0;

  var loadingIcon = $('.log-loading-icon');

  var settings = {
    index: instantData.elasticIndex || "",
    build: instantJSON.build.number,
    builder: instantJSON.build.builder_name,
    step: null,
    codebase: null,
    branch: null,
    pageNum: 1,
    perPage: 1000
  }

  var rtLog = {
    init: function() {
      settings.step = rtLog.getParameterByName('step');
      es.connect(connection, settings);
      searchBox.on('input', function() {
        logContent.empty();
        es.filterAll(this.value, rtLog.renderLog)
      });

      $("#log-cb-errors").click(function() {
        logContent.empty();

        if ($(this).is(':checked')) {
          es.filter("error_type", "error", rtLog.renderLog)
        } else {
          es.clearFilter("error_type", "error", rtLog.renderLog)
        }

      });

      $("#log-cb-warnings").click(function() {
        logContent.empty();

        if ($(this).is(':checked')) {
          es.filter("error_type", "warning", rtLog.renderLog)
        } else {
          es.clearFilter("error_type", "warning", rtLog.renderLog)
        }
      });

      rtLog.initTagFilter();
      loadingIcon.show();
      es.getPage(rtLog.renderLog);
      //rtLog.initPaging();
    },

    // initPaging: function() {
    //   logContent.empty();
    //   es.getPage(rtLog.renderLog);

    //   logContainer.scroll(function() {
    //     if (logContainer.scrollTop() >= $(document).height()) {
    //       if (settings.sort === "desc") {
    //         return
    //       }
    //       loadingIcon.show();
    //       es.nextPage(rtLog.renderLog);
    //     }
    //   });
    // },

    getParameterByName: function(name, url) {
      if (!url) url = window.location.href;
      name = name.replace(/[\[\]]/g, "\\$&");
      var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
        results = regex.exec(url);
      if (!results) return null;
      if (!results[2]) return '';
      return decodeURIComponent(results[2].replace(/\+/g, " "));
    },

    initTagFilter: function() {
      es.getMapping(function(properties) {
        var properties = Object.keys(properties)
        var items = properties.map(function(value, i) { return { id: i, text: value } })
        typeProperties = items
        var fieldSelect = $('#log-field-filter');
        $('#log-field-filter').select2({
          data: items,
          placeholder: "Fields",
          allowClear: true,
        });

        $('#log-field-value').on('input', function() {
          logContent.empty();

          // if (!this.value) {
          //   es.removeFilter(fieldName, rtLog.renderLog)
          // } else {
          //   var fieldName = typeProperties[fieldSelect.val()]
          //   es.filter(fieldName, this.value, rtLog.renderLog, true)
          // }
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
      if (!value.hasOwnProperty('@timestamp')) {
        return
      }

      var timestamp = moment(value['@timestamp']).format('HH:MM:SS')
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
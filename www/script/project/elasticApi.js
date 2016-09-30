/*global define, Handlebars */
define(['elasticsearch', 'lodash'], function(require) {
  "use strict";

  var client,
    esSession = {
      defaultSearchQuery: "",
      mustFilters: {},
      shouldFilters: [],
      pageNumber: 0
    }

  function addMustFilter(name, value) {
    if (name && value) {
      esSession.mustFilters[name] = value
    }
  }

  function removeAllShouldFilter(name) {
    _.remove(esSession.shouldFilters, function(filter) {
      return filter.hasOwnProperty(name)
    });
  }

  function addShouldFilter(name, value, replace) {
    if (!name && !value) {
      return
    }
    if (replace) {
      removeAllShouldFilter(name)
    }
    var entry = {}
    entry[name] = value
    esSession.shouldFilters.push(entry)

  }

  function clearMustFilter(name) {
    delete esSession.mustFilters[name]
  }

  function clearShouldFilter(name, value) {
    var entry = {}
    entry[name] = value
    _.remove(esSession.shouldFilters, entry)
  }

  function getMustMatch(dict) {
    var result = []
    for (var key in dict) {
      if (dict.hasOwnProperty(key)) {
        var obj = {}
        obj[key] = dict[key]
        result.push({ "match": obj });
      }
    }
    return result;
  }

  function getShouldMatch(dict) {
    return esSession.shouldFilters.map(function(value) { return { "match": value } })
  }

  function connect(connection, settings) {
    client = prepareElasticSearch(connection)
    esSession.defaultSearchQuery = initQuery(settings)
  }

  function prepareSearchQuery() {
    var searchQuery = esSession.defaultSearchQuery
    searchQuery.from = esSession.pageNumber * searchQuery.size
    searchQuery.body['query']['constant_score']['query']['bool']['should'] = getShouldMatch(esSession.shouldFilters)
    searchQuery.body['query']['constant_score']['query']['bool']['must'] = getMustMatch(esSession.mustFilters)
    return searchQuery
  }

  function applyDefaultFilters(settings) {
    if (!settings) {
      console.error('Invalid query settings.');
    }

    if (settings.build) {
      addMustFilter("buildNumber", settings.build)
    }

    if (settings.builder) {
      addMustFilter("builderName", settings.builder)
    }

    if (settings.step) {
      addMustFilter("step", settings.step)
    }
  }

  function initQuery(settings) {
    applyDefaultFilters(settings)
    return {
      index: settings.index,
      from: (settings.pageNum - 1) * settings.perPage,
      //size: settings.perPage,
      body: {
        "query": {
          "constant_score": {
            "query": {
              "bool": {
                "must": [],
                "should": []
              }
            }
          }
        },
        "sort": [
          { "@timestamp": { "order": "asc" } }
        ]
      }
    }
  }

  function prepareElasticSearch(connection) {
    if (!connection) {
      console.error('Elastic connection setting was not provided.');
      return
    }

    var client = new elasticsearch.Client(connection);

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

    return client;
  }

  function getPage(renderCallback) {
    esSession.pageNumber = 0
    var query = prepareSearchQuery()
    client.search(query)
      .then(function(resp) {
        renderCallback(resp);
      }, function(err) {
        console.trace(err.message);
      });
  }

  function nextPage(renderCallback) {
    esSession.pageNumber++;
    getPage(renderCallback)
  }

  function parseSearchValue(value) {
    if (!value) {
      removeAllShouldFilter('_all')
      return
    }
    if (value.indexOf(':') === -1) {
      addShouldFilter("_all", value, true)
    }
    var terms = value.split('|');
    var should = [];
    terms.forEach(function(value) {
      var field = value.split(':');
      if (field.length === 2) {
        addShouldFilter(field[0], field[1], true)
      }
    })
  }

  function filterAll(value, renderCallback) {
    parseSearchValue(value)
    getPage(renderCallback)
  }

  function filter(name, value, renderCallback) {
    var searchQuery = esSession.defaultSearchQuery

    addShouldFilter(name, value)

    getPage(renderCallback)
  }

  function clearFilter(name, value, renderCallback) {
    var searchQuery = esSession.defaultSearchQuery;

    clearShouldFilter(name, value);

    getPage(renderCallback);
  }


  function getMapping(callback) {
    client.indices.getMapping({ index: esSession.defaultSearchQuery.index }, function(error, resp) {
      if (error) {
        console.log(error);
      } else {
        var keys = Object.keys(resp)
        if (keys && keys.length) {
          var index = keys[0]
          var properties = resp[index].mappings.logs.properties
          callback(properties)
        }
      }
    })
  }

  var methods = {
    _prepareElasticSearch: prepareElasticSearch,
    _prepareSearchQuery: prepareSearchQuery,
    connect: connect,
    filterAll: filterAll,
    getMapping: getMapping,
    getPage: getPage,
    nextPage: nextPage,
    filter: filter,
    clearFilter: clearFilter
  }

  return methods
})
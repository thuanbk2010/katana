/*global define, Handlebars */
define(['elasticsearch'], function(require) {
  "use strict";

  var client, defaultSearchQuery;

  function connect(connection, settings) {
    client = prepareElasticSearch(connection)
    defaultSearchQuery = prepareSearchQuery(settings)
  }

  function prepareSearchQuery(settings) {
    if (!settings) {
      console.error('Invalid query settings.');
    }

    //var must = [{ "match": { "path": settings.path } }]
    var should = [{ "wildcard": { "message": "*" } }]

    return {
      index: settings.index,
      from: (settings.pageNum - 1) * settings.perPage,
      size: settings.perPage,
      body: {
        "query": {
          "constant_score": {
            "query": {
              "bool": {
                // "must": must,
                "should": should
              }
            }
          }
        }
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

  function search(query, renderCallback) {
    var searchQuery = defaultSearchQuery
    if (query) {
      searchQuery.query = query
    }

    client.search(searchQuery)
      .then(function(resp) {
        renderCallback(resp);
      }, function(err) {
        console.trace(err.message);
      });
  }

  function getPage(renderCallback) {
    client.search(defaultSearchQuery)
      .then(function(resp) {
        renderCallback(resp);
      }, function(err) {
        console.trace(err.message);
      });
  }

  function nextPage(renderCallback) {
    var searchQuery = defaultSearchQuery
    searchQuery.from = searchQuery.from + searchQuery.size

    client.search(searchQuery)
      .then(function(resp) {
        renderCallback(resp);
      }, function(err) {
        console.trace(err.message);
      });
  }

  function filterMessage(value, renderCallback) {
    var searchQuery = defaultSearchQuery
    searchQuery.body.query.constant_score.query.bool.should[0].wildcard.message = value.toLowerCase() || "*";
    searchQuery.from = 0;

    client.search(searchQuery)
      .then(function(resp) {
        renderCallback(resp);
      }, function(err) {
        console.trace(err.message);
      });
  }

  function getMapping(callback) {
    client.indices.getMapping({ index: defaultSearchQuery.index }, function(error, resp) {
      if (error) {
        console.log(error);
      } else {
        var properties = resp[defaultSearchQuery.index].mappings.logs.properties ||
          resp[defaultSearchQuery.index].mappings.properties
        callback(properties)
      }
    })
  }

  var methods = {
    _prepareElasticSearch: prepareElasticSearch,
    _prepareSearchQuery: prepareSearchQuery,
    connect: connect,
    filterMessage: filterMessage,
    getMapping: getMapping,
    getPage: getPage,
    nextPage: nextPage,
    filter: function(filters) {}
  }

  return methods

})
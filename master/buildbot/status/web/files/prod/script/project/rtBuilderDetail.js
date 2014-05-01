define(["jquery","realtimePages","helpers","dataTables","handlebars","extend-moment","libs/jquery.form","text!templates/builderdetail.handlebars","timeElements"],function(e,t,n,r,i,s,o,u,a){var f,l,c,h,p=Handlebars.compile(u);return f={init:function(){c=f.currentBuildsTableInit(e("#rtCurrentBuildsTable")),h=f.pendingBuildsTableInit(e("#rtPendingBuildsTable"));var r=t.defaultRealtimeFunctions();r.project=f.rtfProcessCurrentBuilds,r.pending_builds=f.rtfProcessPendingBuilds,t.initRealtime(r);var i=e(".dataTables_wrapper .top");window.location.search!==""&&n.codeBaseBranchOverview(e("#brancOverViewCont"))},rtfProcessCurrentBuilds:function(e){a.clearTimeObjects(c),c.fnClearTable();try{console.log(e),e.currentBuilds!==undefined&&(c.fnAddData(e.currentBuilds),a.updateTimeObjects()),a.updateTimeObjects()}catch(t){console.log(t)}},rtfProcessPendingBuilds:function(e){a.clearTimeObjects(h),h.fnClearTable(),n.selectBuildsAction(h);try{console.log(e),h.fnAddData(e),a.updateTimeObjects()}catch(t){}},currentBuildsTableInit:function(e){var t={};return t.aoColumns=[{mData:null},{mData:null},{mData:null},{mData:null}],t.aoColumnDefs=[{aTargets:[0],sClass:"txt-align-left",mRender:function(e,t,n){return p({showNumber:!0,data:n})}},{aTargets:[1],sClass:"txt-align-left"},{aTargets:[2],sClass:"txt-align-left"},{aTargets:[3],sClass:"txt-align-left"}],r.initTable(e,t)},pendingBuildsTableInit:function(t){var n={};return n.aoColumns=[{mData:null},{mData:null},{mData:null}],n.aoColumnDefs=[{aTargets:[0],sClass:"txt-align-left",mRender:function(e,t,n){return s.getDateFormatted(n.submittedAt)}},{aTargets:[1],sClass:"txt-align-left",mRender:function(e,t,n){return p({pendingBuildWait:!0})},fnCreatedCell:function(t,n,r){console.log(e(t).find(".waiting-time")),a.addElapsedElem(e(t).find(".waiting-time-js"),r.submittedAt)}},{aTargets:[2],sClass:"txt-align-right",mRender:function(e,t,n){return p({removeBuildSelector:!0,data:n})}}],r.initTable(t,n)}},f});
define(["helpers","libs/jquery.form","text!templates/popups.mustache","mustache"],function(e,t,n,r){var i;return i={init:function(){var t=$("#tablesorterRt");t.delegate("a.popup-btn-json-js","click",function(e){e.preventDefault(),i.showjsonPopup($(this).data())}),$(".popup-btn-js-2").click(function(e){e.preventDefault(),i.nonAjaxPopup($(this))}),t.delegate(".popup-btn-js","click",function(t){t.preventDefault();var n=document.URL,r=document.createElement("a");r.href=n;var s=encodeURIComponent($(this).attr("data-builderName")),o="{0}//{1}/json/pending/{2}/?".format(r.protocol,r.host,s),u=e.codebasesFromURL({}),a=e.urlParamsToString(u);i.pendingJobs(o+a)}),$("#getBtn").click(function(e){e.preventDefault(),i.codebasesBranches()}),t.delegate(".ajaxbtn","click",function(e){e.preventDefault(),i.externalContentPopup($(this))}),$(".ajaxbtn").click(function(e){e.preventDefault(),i.externalContentPopup($(this))})},showjsonPopup:function(t){var i=r.render(n,t),s=$(r.render(n,{MoreInfoBoxOuter:!0},{partial:i}));$("body").append(s),t.showRunningBuilds!=undefined&&e.delegateToProgressBar($("div.more-info-box-js div.percent-outer-js")),e.jCenter(s).fadeIn("fast",function(){e.closePopup(s)})},validateForm:function(e){var t=$(".command_forcebuild",e),i=":button, :hidden, :checkbox, :submit";$(".grey-btn",t).click(function(e){var s=$("input",t).not(i),o=s.filter(function(){return this.name.indexOf("revision")>=0}),u=o.filter(function(){return this.value===""});if(u.length>0&&u.length<o.length){o.each(function(){$(this).val()===""?$(this).addClass("not-valid"):$(this).removeClass("not-valid")}),$(".form-message",t).hide();if(!$(".error-input",t).length){var a=r.render(n,{errorinput:"true",text:"Fill out the empty revision fields or clear all before submitting"}),f=$(a);$(t).prepend(f)}e.preventDefault()}})},nonAjaxPopup:function(t){var n=t.next($(".more-info-box-js")).clone();n.appendTo($("body")),e.jCenter(n).fadeIn("fast",function(){e.closePopup(n)}),$(window).resize(function(){e.jCenter(n)})},pendingJobs:function(t){var i=r.render(n,{preloader:"true"}),s=$(i);$("body").append(s).show();var o=document.URL,u=document.createElement("a");u.href=o;var a=u.protocol+"//"+u.host+u.pathname;$.ajax({url:t,cache:!1,dataType:"json",success:function(t){s.remove();var i=r.render(n,{pendingJobs:t,showPendingJobs:!0,cancelAllbuilderURL:t[0].builderURL}),o=$(r.render(n,{MoreInfoBoxOuter:!0},{partial:i})),u=o.find(".waiting-time-js");u.each(function(n){e.startCounter($(this),t[n].submittedAt)}),o.appendTo("body"),e.jCenter(o).fadeIn("fast",function(){e.closePopup(o)})}})},codebasesBranches:function(){var t=$("#pathToCodeBases").attr("href"),s=r.render(n,{preloader:"true"}),o=$(s);$("body").append(o).show();var u=i.htmlModule("Select branches");$(u).appendTo("body"),$.get(t).done(function(t){require(["selectors"],function(n){var r=$("#content1");o.remove();var i=$(t).find("#formWrapper");i.children("#getForm").attr("action",window.location.href);var s=i.find('.blue-btn[type="submit"]').val("Update");i.appendTo(r),e.jCenter(u).fadeIn("fast",function(){n.init(),s.focus(),e.closePopup(u)}),$(window).resize(function(){e.jCenter(u)})})})},customTabs:function(){$(".tabs-list li").click(function(e){var t=$(this).index();$(this).parent().find("li").removeClass("selected"),$(this).addClass("selected"),$(".content-blocks > div").each(function(e){$(this).index()!=t?$(this).hide():$(this).show()})})},externalContentPopup:function(t){var n=t.attr("data-popuptitle"),r=t.attr("data-b"),s=t.attr("data-indexb"),o=t.attr("data-returnpage"),u=t.attr("data-rt_update"),a=t.attr("data-contenttype"),f=t.attr("data-b_name"),l=$('<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>'),c=$("body");c.append(l);var h=i.htmlModule(n);h.appendTo(c);var p={rt_update:u,datab:r,dataindexb:s,builder_name:f,returnpage:o},d=window.location.search.substring(1),v=d.split("&");$.each(v,function(e,t){var n=t.split("=");n[0].indexOf("_branch")>=0&&(p[n[0]]=n[1])});var m=location.protocol+"//"+location.host+"/forms/forceBuild";$.get(m,p).done(function(t){var n=$("#content1");l.remove(),$(t).appendTo(n),e.tooltip(n.find($(".tooltip"))),a==="form"&&(e.setFullName($("#usernameDisabled, #usernameHidden",n)),i.validateForm(n)),e.jCenter(h).fadeIn("fast"),$(window).resize(function(){e.jCenter(h)}),e.closePopup(h),o!==undefined&&n.find("form").ajaxForm({beforeSubmit:function(){c.append(l),n.closest(".more-info-box").find(".close-btn").click()},success:function(e){requirejs(["realtimePages"],function(t){l.remove();var n=o.replace("_json","");t.updateSingleRealTimeData(n,e)})}})})},htmlModule:function(e){var t=$('<div class="more-info-box remove-js"><span class="close-btn"></span><h3 class="codebases-head">'+e+"</h3>"+'<div id="content1"></div></div>');return t}},i});
/*global define*/
define(['jquery', 'libs/jquery.form', 'libs/jquery.numeric'], function ($) {
    "use strict";

    var COLOR_BLIND_CSS = "color-blind-mode";

    var privFunc = {
        initColorBlindBtn: function () {
            var $colorBtn = $("#colorBlindMode"),
                $colorField = $("#colorBlind_setting"),
                $body = $("body"),
                $colorBlindOpt = $colorBtn.parent().find("#colorBlindOpt");

            function setColorField(activated) {
                var val = activated ? "1" : "0";
                $colorField.val(val);
            }

            setColorField($body.hasClass(COLOR_BLIND_CSS));

            $colorBtn.bind("click.katana", function () {
                var colorBlindActivated = $body.hasClass(COLOR_BLIND_CSS);
                if (colorBlindActivated === true) {
                    $body.removeClass(COLOR_BLIND_CSS);
                } else {
                    $body.addClass(COLOR_BLIND_CSS);
                }
                setColorField(!colorBlindActivated);
            });
        }
    };

    return {
        init : function () {
            privFunc.initColorBlindBtn();

            $('input[type=number]').numeric({ decimal: false, negative : false });
        }
    };
});
/**
 * DataTable jQuery UI Loader
 * 
 * Ensures jQuery UI is available for Bokeh DataTable.reorderable functionality.
 * Injects minimal CSS for drag/drop support and monitors jQuery readiness.
 */
(function () {
    var retries = 0;
    var maxRetries = 50;
    var uiCss = '.ui-draggable{cursor:move}.ui-draggable-dragging{opacity:0.7;z-index:1000}.ui-sortable{cursor:pointer}.ui-sortable-handle{cursor:grab;user-select:none}.ui-sortable-handle:active{cursor:grabbing}';

    function injectUIStyles() {
        if (document.getElementById('bokeh-ui-styles')) {
            return;
        }
        var style = document.createElement('style');
        style.id = 'bokeh-ui-styles';
        style.textContent = uiCss;
        document.head.appendChild(style);
        console.log('[DataTable] jQuery UI styles injected');
    }

    function waitForjQuery() {
        // Check if jQuery and jQuery UI draggable are available
        if (typeof window.jQuery !== 'undefined' && typeof jQuery.fn.draggable !== 'undefined') {
            injectUIStyles();
            console.log('[DataTable] jQuery UI ready for reorderable');
            return;
        }

        if (retries++ < maxRetries) {
            setTimeout(waitForjQuery, 100);
        } else {
            console.warn('[DataTable] jQuery UI not available after ' + (retries * 100) + 'ms');
        }
    }

    // Start waiting when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', waitForjQuery);
    } else {
        waitForjQuery();
    }
})();

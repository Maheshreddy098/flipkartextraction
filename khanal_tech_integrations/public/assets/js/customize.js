
$(function () {
    var current = location.pathname;
    $('.sidebar-left  li a').each(function () {
        var $this = $(this);
        if ($this.attr('href') == current) {
            $this.addClass('active');
            $this.parent().parent().addClass('show');
        }
    })
})
 


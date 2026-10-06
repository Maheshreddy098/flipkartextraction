
$(function () {

  value = location.protocol + '//' + location.host + location.pathname
  if (window.location.href == value) {
    // var start = moment().subtract(29, 'days');
    // var end = moment();
    function cb(start, end) {
      $('#LogisticDatereportrange span').html(start.format('MMMM D, YYYY') + ' - ' + end.format('MMMM D, YYYY'));
    }
  }
  else {
    url = new URL(window.location.href)
    var startdate = url.searchParams.get("startDate");
    var enddate = url.searchParams.get("endDate");
    var start = new Date(startdate).toDateString().slice(4, 15);
    var end = new Date(enddate).toDateString().slice(4, 15);
    if (start == 'lid Date') {
      function cb(start, end) {
        $('#LogisticDatereportrange span').html(start.format('MMMM D, YYYY') + ' - ' + end.format('MMMM D, YYYY'));
      }
    }
    else {
      $('#LogisticDatereportrange span').html(start + ' - ' + end);
    }
  }


  start = moment().subtract(29, 'days');
  end = moment();
  $('#LogisticDatereportrange').daterangepicker({
    startDate: start,
    endDate: end,

    ranges: {
      'Today': [moment(), moment()],
      'Yesterday': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
      'Last 7 Days': [moment().subtract(6, 'days'), moment()],
      'Last 30 Days': [moment().subtract(29, 'days'), moment()],
      'This Month': [moment().startOf('month'), moment().endOf('month')],
      'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
    }
  },
    cb
  );

  cb(start, end);



});

$('#LogisticDatereportrange').on('apply.daterangepicker', function (ev, picker) {
  var startDate = picker.startDate.format('YYYY-MM-DD');
  var endDate = picker.endDate.format('YYYY-MM-DD');
  var url = "/intranet/myorder?startDate=" + startDate + "&endDate=" + endDate;
  window.location.href = url;

});



$(document).ready(function () {
  $('#myorderTable').DataTable({
  dom: 'lBfrtip',
    buttons: [
      'csv', 'excel', 'print'
    ],
    
    columnDefs: [
      {
        target: 9,
        visible: false,
        searchable: false,
      },
      {
        target: 10,
        visible: false,
        searchable: false,
      },
      {
        target: 11,
        visible: false,
        searchable: false,
      },
    ],
    order: [[0, 'asc']],
  })
});

function myFunction() {
  var div = document.getElementById("HideDiv");
  // var expanddiv = document.getElementById("BuildToggle");
  if (div.style.display === "none") {
      div.style.display = "block";
      $("#BuildToggle").removeClass('col-xl-12')
      $("#BuildToggle").addClass('col-xl-9')
      // alert('show')
  } else {
      div.style.display = "none";
      $("#BuildToggle").removeClass('col-xl-9')
      $("#BuildToggle").addClass('col-xl-12')
      // alert('hide')
  }
} 


$(document).ready(function () {
  url = new URL(window.location.href)
  var startDate = url.searchParams.get("startDate");
  var endDate = url.searchParams.get("endDate");
  if (startDate == null && endDate == null) {
    $('#SalePersonSearch').hide()
  }
  else {

  }
  $.ajax({
    method: "GET",
    url: "/",
    data: {
      cmd: "khanal_tech_integrations.www.intranet.myorder.get_salespersonsforsessiouser",
    },
    dataType: "json",
    success: function (response) {
      arrayLength = response.message.length
      for (var i = 0; i < arrayLength; i++) {
        var tagOption = ('<option value=' + response.message[i].salesperson_code + '>' + response.message[i].salesperson_name + '</option>');
        $('#MultipleSelect').append(tagOption);
      }
      var multipleCancelButton = new Choices('#MultipleSelect', {
        removeItemButton: true,
        maxItemCount: 10,
        searchResultLimit: 50,
        renderChoiceLimit: 50
      });
    }
  })
});






function getSelectValues(select) {
  var result = [];
  var options = select && select.options;
  var opt;
  for (var i = 0, iLen = options.length; i < iLen; i++) {
    opt = options[i];
    if (opt.selected) {
      result.push(opt.value || opt.text);
    }
  }




  url = new URL(window.location.href)
  var startDate = url.searchParams.get("startDate");
  var endDate = url.searchParams.get("endDate");
  var url = "/intranet/myorder?startDate=" + startDate + "&endDate=" + endDate + '?' + '&SalesPersonCode=' + result;
  window.location.href = url;


  return result;
}




function DeliveryStatusModal(TrackinId) {
  // alert(TrackinId)
  $.ajax({
    method: "GET",
    url: "/",
    dataType: 'json',
    contentType: 'application/json; charset=utf-8',
    // traditional:true,
    data: {
      cmd: "khanal_tech_integrations.www.intranet.myorder.delivery_status",
      TrackinId: TrackinId
    },
    dataType: "json",
    success: function (response) {

      $('#orderDeatils').html(response.message.shipment.refNo)
      $('#owner').html(response.message.shipment.toAttention)
      // var date = new Date(response.message.shipment.edd);
      console.log(response.message,'message')
      $('#edd').html(response.message.shipment.edd)
      $('#status').html(response.message.shipment.status)
     
      trackinglenght = response.message.shipment.tracking.length

      tracking=response.message.shipment.tracking
        
    
let sortableData = [];
let nextDayData = [];

tracking.forEach(function(data) {
  let dateParts = data.date.split(" ");
  let date = dateParts[0];
  let time = dateParts[1];
  let period = dateParts[2];
  
  let sortableDate = new Date(date + " " + time + " " + period);
  
  if (period === "am" && time === "12:00:00") {
    nextDayData.push({
      sortableDate: sortableDate,
      data: data
    });
  } else {
    sortableData.push({
      sortableDate: sortableDate,
      data: data
    });
  }
});

sortableData.sort(function(a, b) {
  return b.sortableDate - a.sortableDate;
});

nextDayData.sort(function(a, b) {
  return b.sortableDate - a.sortableDate;
});

let sortedData = sortableData.concat(nextDayData);

console.log(sortedData.map(function(sortedDatum) {
  return sortedDatum.data;
}));
      
      $('#ullist li').remove();
      for (var i = 0; i < trackinglenght; i++) {
      
        switch (response.message.shipment.tracking[i].status) {
          case "DELIVERED":
            var experiencecontent = '<li>' +
              '<div class="time">' +
              response.message.shipment.tracking[i].date +
              '</div>' +
              '<p>' +
              response.message.shipment.tracking[i].description +
              '</p>' +
              '<p>' +
              '<div class="badge rounded-pill badge-soft-success ">' +
              'DELIVERED' +
              '<span class="fas fa-check-double ms-1 "  data-fa-transform="shrink-2">' +
              '</span>' +
              '</div>' +
              ' </p>' +
              '</li>';

            $("#ullist").append(experiencecontent);
            break;
          case "OUT FOR DELIVERY":
            var experiencecontent = '<li>' +
              '<div class="time">' +
              response.message.shipment.tracking[i].date +
              '</div>' +
              '<p>' +
              response.message.shipment.tracking[i].description +
              '</p>' +
              '<p>' +
              '<div class="badge rounded-pill badge-soft-warning ">' +
              'OUT FOR DELIVERY' +
              '<span class="fas fa-stop-circle ms-1" data-fa-transform="shrink-2">' +
              '</span>' +
              '</div>' +
              ' </p>' +
              '</li>';

            $("#ullist").append(experiencecontent);
            break;
          case "IN-TRANSIT":
            var experiencecontent = '<li>' +
              '<div class="time">' +
              response.message.shipment.tracking[i].date +
              '</div>' +
              '<p>' +
              response.message.shipment.tracking[i].description +
              '</p>' +
              '<p>' +
              '<div class="badge rounded-pill badge-soft-secondary ">' +
              'IN-TRANSIT' +
              '<span class="fas fa-route ms-1" data-fa-transform="shrink-2">' +
              '</span>' +
              '</div>' +
              ' </p>' +
              '</li>';

            $("#ullist").append(experiencecontent);
            break;
          case "DISPATCHED":
            var experiencecontent = '<li>' +
              '<div class="time">' +
              response.message.shipment.tracking[i].date +
              '</div>' +
              '<p>' +
              response.message.shipment.tracking[i].description +
              '</p>' +
              '<p>' +
              '<div class="badge rounded-pill badge-soft-info ">' +
              'DISPATCHED' +
              '<span  class="fas fa-shipping-fast ms-1" data-fa-transform="shrink-2">' +
              '</span>' +
              '</div>' +
              ' </p>' +
              '</li>';

            $("#ullist").append(experiencecontent);
            break;
          case "BOOKED":
            var experiencecontent = '<li>' +
              '<div class="time">' +
              response.message.shipment.tracking[i].date +
              '</div>' +
              '<p>' +
              response.message.shipment.tracking[i].description +
              '</p>' +
              '<p>' +
              '<div class="badge rounded-pill badge-soft-dark ">' +
              'BOOKED' +
              '<span class="fas fa-bookmark ms-1" data-fa-transform="shrink-2">' +
              '</span>' +
              '</div>' +
              ' </p>' +
              '</li>';

            $("#ullist").append(experiencecontent);
            break;
          case "ARRIVED AT DESTINATION":
            var experiencecontent = '<li>' +
              '<div class="time">' +
              response.message.shipment.tracking[i].date +
              '</div>' +
              '<p>' +
              response.message.shipment.tracking[i].description +
              '</p>' +
              '<p>' +
              '<div class="badge rounded-pill badge-soft-primary ">' +
              'ARRIVED AT DESTINATION' +
              '<span class="fas fa-check ms-1" data-fa-transform="shrink-2">' +
              '</span>' +
              '</div>' +
              ' </p>' +
              '</li>';

            $("#ullist").append(experiencecontent);
            break;

        }


      }
    }

  })
}


function ClearFilter(){
  url = new URL(window.location.href)
  var startDate = url.searchParams.get("startDate");
  var endDate = url.searchParams.get("endDate");
  var url = "/intranet/myorder?startDate=" + startDate + "&endDate=" + endDate ;
  window.location.href = url;
}




// const sortedTracking = tracking.sort((a, b) => {
//   const dateA = new Date(a.date);
//   const dateB = new Date(b.date);

//   if (a.date.includes("12:00:00 am")) {
//     dateA.setDate(dateA.getDate() + 1);
//   }

//   if (b.date.includes("12:00:00 am")) {
//     dateB.setDate(dateB.getDate() + 1);
//   }

//   return dateA - dateB;
// });

// const formattedTracking = sortedTracking.map(entry => {
//   let [date, time] = entry.date.split(" ");
//   let [month, day, year] = date.split("-");
//   let [hour, minute, second] = time.split(":");

//   if (time === "12:00:00 am") {
//     day = (parseInt(day) + 1).toString();
//     time = "00:00:00";
//   }

//   return {
//     ...entry,
//     date: `${day}-${month}-${year} ${time}`
//   };
// });

// console.log(formattedTracking);
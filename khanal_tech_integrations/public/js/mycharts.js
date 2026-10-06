document.addEventListener('DOMContentLoaded', function () {
    // --- Data Access ---
    const rawData = window.rawData || [];
    const warehouseData = window.warehouseData || [];
    const vendorData = window.vendorData || [];
    
    
    // --- Milk Procurement Line Chart ---
    const groupedData = {};
    rawData.forEach(row => {
        const month = row.supplied_date;
        const qty = parseFloat(row.qty_ltr) || 0;
        groupedData[month] = (groupedData[month] || 0) + qty;
    });

    const procurementLabels = Object.keys(groupedData).sort();
    const procurementValues = procurementLabels.map(month => groupedData[month]);

    const ctx1 = document.getElementById('milkProcurementLineChart');
    if (ctx1) {
        new Chart(ctx1.getContext('2d'), {
            type: 'line',
            data: {
                labels: procurementLabels,
                datasets: [{
                    label: 'Milk Procured (Litres)',
                    data: procurementValues,
                    borderColor: '#4e73df',
                    backgroundColor: 'rgba(78, 115, 223, 0.05)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Litres' }
                    },
                    x: {
                        title: { display: true, text: 'Month' }
                    }
                }
            }
        });
    }

    // ---Total Warehouse Bar Chart ---
    // const warehouseLabels = warehouseData.map(row => row.item_code);
    // const warehouseOpenQty = warehouseData.map(row => parseFloat(row.open_qty) || 0);

    // const ctx2 = document.getElementById('warehouseBarChart');
    // if (ctx2) {
    //     new Chart(ctx2.getContext('2d'), {
    //         type: 'bar',
    //         data: {
    //             labels: warehouseLabels,
    //             datasets: [{
    //                 label: 'Open Quantity',
    //                 data: warehouseOpenQty,
    //                 backgroundColor: 'rgba(75, 192, 192, 0.5)',
    //                 borderColor: 'rgba(75, 192, 192, 1)',
    //                 borderWidth: 1
    //             }]
    //         },
    //         options: {
    //             responsive: true,
    //             scales: {
    //                 y: {
    //                     beginAtZero: true,
    //                     title: { display: true, text: 'Item Code' }
    //                 },
    //                 x: {
    //                     title: { display: true, text: 'Quantity' }
    //                 }
    //             }
    //         }
    //     });
    // }


    // --- Warehouse Least Bar Chart ---
   // Step 1: Group item codes by their quantity
const quantityMap = {};

warehouseData.forEach(row => {
    const qty = parseFloat(row.open_qty) || 0;
    const item = row.item_code;
    if (!quantityMap[qty]) {
        quantityMap[qty] = [];
    }
    quantityMap[qty].push(item);
});

// Step 2: Prepare labels and values
const warehouseLabels = Object.keys(quantityMap).sort((a, b) => a - b);  // Quantities
const warehouseItemCounts = warehouseLabels.map(qty => quantityMap[qty].length);  // Number of items

// Step 3: Draw pie chart
const ctx2 = document.getElementById('warehouseBarChart');
if (ctx2) {
    new Chart(ctx2.getContext('2d'), {
        type: 'pie',
        data: {
            labels: warehouseLabels,
            datasets: [{
                label: 'Open Quantity',
                data: warehouseItemCounts,
                backgroundColor: warehouseLabels.map((_, i) =>
                    `hsl(${(i * 360) / warehouseLabels.length}, 70%, 60%)`
                ),
                borderColor: '#fff',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,            
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const qty = context.label;
                            const items = quantityMap[qty] || [];
                            return `Qty: ${qty} | Items: ${items.join(", ")}`;
                        }
                    }
                },
                legend: {
                    position: 'right'
                }
            }
        }
    });
}



    // --- Vendor Pie Chart ---
const vendorLabels = vendorData.map(row => row.card_name);
const vendorQuantities = vendorData.map(row => parseFloat(row.total_quantity_supplied) || 0);

// Use bright solid colors (more can be added if needed)
const backgroundColors = [
    '#e6194b', // Red
    '#3cb44b', // Green
    '#ffe119', // Yellow
    '#4363d8', // Blue
    '#f58231', // Orange
    '#911eb4', // Purple
    '#46f0f0', // Cyan
    '#f032e6', // Magenta
    '#bcf60c', // Lime
    '#fabebe', // Pink
    '#008080', // Teal
    '#e6beff', // Lavender
    '#9a6324', // Brown
    '#fffac8', // Cream
    '#800000', // Maroon
    '#aaffc3', // Mint
    '#808000', // Olive
    '#ffd8b1', // Peach
    '#000075', // Navy
    '#808080'  // Gray
];

const borderColors = backgroundColors;

const ctx3 = document.getElementById('vendorPieChart');
if (ctx3) {
    new Chart(ctx3.getContext('2d'), {
        type: 'bar',
        data: {
            labels: vendorLabels,
            datasets: [{
                label: 'Total Quantity Supplied (Litres)',
                data: vendorQuantities,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Total Quantity Supplied by Vendor (Litres)'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Litres'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Vendors'
                    }
                }
            }
        }
    });
}

});

try {
    const ctx = document.getElementById('power_radar').getContext('2d');
    const power_radar = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['QB', 'RB', 'WR', 'TE', 'Picks', 'Starters', 'Bench'],
            datasets: [{
                label: jsonData.display_name,
                data: [jsonData.qb_rank, jsonData.rb_rank, jsonData.wr_rank, jsonData.te_rank, jsonData.picks_rank, jsonData.starters_rank, jsonData.bench_rank],
                backgroundColor: 'rgb(39, 125, 161, .95)',
                borderColor: 'rgb(67, 170, 139, 1.0)',
                borderWidth: 3
            }]
        },
        options: {
            font: {
                size: 16,
                weight: "bolder"
            },
            plugins: {
                tooltip: {
                    bodyColor: '#F9C74F',
                    backgroundColor: 'rgba(67, 170, 139, .8)',
                }
            },

            scales: {

                r: {
                    reverse: true,
                    max: totalRosters,
                    min: 1,
                    beginAtZero: false,

                    ticks: {
                        stepSize: 4,
                        display: false
                    }, grid: {
                        color: 'rbg(118, 118, 118)', // Change the grid color
                    },
                },
            },

        }

    });
} catch (e) {

}
// document.getElementById('demo').innerHTML = "This was created with javascript"
var ctx = document.getElementById("lineChart").getContext("2d")
var lineChart = new Chart(ctx, {
    type: "line",
    data: {
        labels: {{ labels | safe }},
datasets: [
    {
        label: "data points",
        data: {{ values | safe }},
    fill: false,
    borderColor: "rgb(75,192,192)",
    lineTension: 0.1
                    }
]
                    },
options: {
    response: false
}
                })
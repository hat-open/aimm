import * as plotly from 'plotly.js/dist/plotly.js';
import 'main/index.scss';


export function vt() {
    return plot();
}


export function on_radio_switch(model_type){
    console.log("HELLO " + model_type);

//     r.get('remote', 'timeseries', 'reading')
       hat.conn.send('timeseries', {'model': model_type});
//     let swValue = r.get('remote', 'adapter', String(i) + '+' + '0');
}
export function trigger_notebook(){
        hat.conn.send('timeseries', {'notebook': 1});
}

export function plot() {
    const layout = {
        title: 'Timeseries model testing',
        xaxis: {
            title: 'Hour',
            showgrid: true,
            range: [0, 72]
        },
        yaxis: {
            title: 'CO concentration',
            showline: false,
            range: [600, 2100]
        }
    };
    const config = {
        displayModeBar: true,
        responsive: true,
        staticPlot: true
    };

    const reading_trace = {
        x: r.get('remote', 'timeseries', 'reading').keys(),
        y: r.get('remote', 'timeseries', 'reading'),
        line: { shape: 'spline' },
        type: 'scatter',
        name: 'Reading'
    };
    const forecast_trace = {
        x: r.get('remote', 'timeseries', 'forecast').map((_, k) => k + 47),
        y: r.get('remote', 'timeseries', 'forecast'),
        line: { shape: 'spline' },
        type: 'scatter',
        name: 'Forecast'
    };
    const data = [reading_trace, forecast_trace];



    return ['div',
        [
            ["label",{props: {for: 'input1'}},' Previous Model '],
            ["input",{props: {disabled: true, id: 'input1',value:  r.get('remote','timeseries','model_before')}}],
            ["label",{props: {for: 'input2'}},' Current Model '],
            ["input",{props: {disabled: true, id: 'input2',value:  r.get('remote','timeseries','model_now')}}]
        ],

        ['div',
            [["input",
            {
                props: {type: 'radio', id: 'id1', name: 'modelSelect', value: 'linear' },
                on: { click: () => on_radio_switch("linear") }

            }],
            ["label",{props: {for: 'id1'}},'Linear'],
            ["input",
            {
                props: {type: 'radio', id: 'id2', name: 'modelSelect', value: 'MultiOutputSVR' },
                on: { click: () => on_radio_switch("MultiOutputSVR") }

            }],
            ["label",{props: {for: 'id2'}},'MultiOutputSVR'],
            ["input",
            {
                props: {type: 'radio', id: 'id3', name: 'modelSelect', value: 'constant' },
                on: { click: () => on_radio_switch("constant") }

            }],
            ["label",{props: {for: 'id3'}},'constant']]
        ],
        ["button",
            {
                props: {type: 'checkbox', id: 'id_checkbox', name: 'triggerNotebook', value: 'triggerNotebook' },
                on: { click: () => trigger_notebook() }

            },
            "Run model"
            ],
        ["label",{props: {for: 'id_checkbox'}},''],
        ['div.plot', {
            plotData: data,
            props: {
                style: 'height: 100%'
            },
            hook: {
                insert: vnode => plotly.newPlot(vnode.elm, data, layout, config),
                update: (oldVnode, vnode) => {
                    if (u.equals(oldVnode.data.plotData, vnode.data.plotData)) return;
                    plotly.react(vnode.elm, data, layout, config);
                },
                destroy: vnode => plotly.purge(vnode.elm)
            }
        }
        ]

    ];

//             'attrs': {
//
//             },
//
//             on: {
//                 //click: () => trafoChange("Bus"),
//                 mouseover: () => {
//                     onHover(right - 10, down - length - 30, 20, length * 2 * 1.4, 'bus', id);
//
//                 }
//
//
//
//             }


}

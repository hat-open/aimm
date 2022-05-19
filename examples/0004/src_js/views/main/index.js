import * as plotly from 'plotly.js/dist/plotly.js';
import 'main/index.scss';


export function vt() {
    return plot();
}

export function plot() {
    let l = r.get('remote', 'timeseries','timestamps','reading').length
    const layout = {
        title: 'Timeseries anomaly model testing',
        xaxis: {
            title: 'Timestamp',
            showgrid: true,
            range: [
                // '2013-07-06 06:00:00',
                // '2013-10-06 06:00:00'

                // r.get('remote', 'timeseries','timestamps','reading')[0],
                // r.get('remote', 'timeseries','timestamps','reading')[l-1]
            ]
        },
        yaxis: {
            title: 'Temperature',
            showline: false,
            // range: [0, 2]
        }
    };
    const config = {
        displayModeBar: true,
        responsive: true,
        staticPlot: true
    };

    const reading_trace = {
        x: r.get('remote', 'timeseries','timestamps','reading'),
        y: r.get('remote', 'timeseries','values','reading'),
        line: { shape: 'spline' },
        type: 'scatter',
        name: 'Reading'
    };
    const forecast_trace = {
        x: r.get('remote', 'timeseries','timestamps','forecast'),
        y: r.get('remote', 'timeseries','values','forecast'),
        // line: { shape: 'spline' },
        mode: 'markers',
        type: 'scatter',
        name: 'Forecast'
    };
    const data = [reading_trace, forecast_trace];

    const cur_model_name = r.get('remote','timeseries','info','new_current_model');
    const setting_name = r.get('remote','timeseries','info','setting','name');

    function on_radio_switch(model_type){
        console.log("Picked: " + model_type);
        hat.conn.send('timeseries', {'action': 'model_change', 'model': model_type});
    }

    function change_button_color(model_type){
        const models = r.get('remote','timeseries','info','model_state','models');
        if (!models) return '';
        for (const [key, value] of Object.entries(models)) {
          if (value.split(".").at(-1) === model_type ) return 'border: 3px solid green;'

        }
        return '';
    }

    const generate_setting_inputs = function () {
            if (!r.get('remote','timeseries','info','setting')) return;

            var t = Object.entries(r.get('remote','timeseries','info','setting'))
                .map(function([key,value],index) {
                          return ["div",[
                ["label",{props: {for: 'input1'}}, key  ],
                ["input",{
                            props: {
                                disabled: !cur_model_name,
                                id: 'input1',
                                value: value },
                            on: {
                                change: function (e) {
                                    console.log("changed to: " + e.target.value);
                                    hat.conn.send('timeseries',
                                     {
                                     'action': 'setting_change',
                                     [key]: e.target.value});
                                }
                            }
                        }],
                    ]]

                   });

             return ["div",t];
    }

    const generate_model_buttons = function () {
        if (!r.get('remote','timeseries','info','supported_models')) return;

        var t = r.get('remote','timeseries','info','supported_models').map(function(value,index) {
                      return [
                    "button",
                    {
                        props: {
                            disabled: cur_model_name === value,
                            type: 'checkbox', id: 'id1',
                            name: 'modelSelect',
                            style: change_button_color(value),
                            value: 'Forest' },
                        on: {  click: () => on_radio_switch(value) }
                    },
                    value
                    ]
               });

         return ["div",t];
    }

    return ['div',
        [

            ["label",{props: {for: 'input2'}},' Current Model '],
            ["input",{props: {disabled: true, id: 'input2',value: cur_model_name }}],
            ["br"],
            generate_setting_inputs(),
            ["br"],
        ],
        ["br"], ["br"],
        ['div',generate_model_buttons()],
        ['div.plot',
            {
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
}

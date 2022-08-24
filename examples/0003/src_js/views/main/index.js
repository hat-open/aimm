import * as plotly from 'plotly.js/dist/plotly.js';
import 'main/index.scss';
import redux from 'redux';


export function vt() {
    return plot();
}

export function plot() {
    let l = r.get('remote', 'timeseries','timestamps','reading').length;

    const dateValue = new Date(r.get('remote', 'timeseries','timestamps','reading')[l-1]);
    dateValue.setHours(dateValue.getHours() + 48);
    const x_r = dateValue.getFullYear()+ "-" + (dateValue.getMonth()+1) + "-" + dateValue.getDate() + " "
		+ dateValue.getHours() + ":00:00";

    const layout = {
        title: 'Timeseries anomaly/forecast model testing',
        xaxis: {
            title: 'Timestamp',
            showgrid: true,
            range: [
                r.get('remote', 'timeseries','timestamps','reading')[0],
                x_r
            ]
        },
        yaxis: {
            title: 'Temperature',
            showline: false,
            range: [16, 30]
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

    const anomaly_trace = {
        x: r.get('remote', 'timeseries','timestamps','anomaly'),
        y: r.get('remote', 'timeseries','values','anomaly'),
        mode: 'markers',
        type: 'scatter',
        name: 'Anomaly'
    };

    const forecast_trace = {
        x: r.get('remote', 'timeseries','timestamps','forecast').map((k) => {
            const dateValue = new Date(k);

            dateValue.setHours(dateValue.getHours() + 24);
            return dateValue.getFullYear()+ "-" + (dateValue.getMonth()+1) + "-" + dateValue.getDate() + " "
		   + dateValue.getHours() + ":00:00";

        }),
        y: r.get('remote', 'timeseries','values','forecast'),
        line: { shape: 'spline' },
        type: 'scatter',
        name: 'Forecast'
    };

    const data = [reading_trace, anomaly_trace,forecast_trace];

    const cur_anomaly_model_name = r.get('remote','timeseries','info','anomaly','new_current_model');
    const cur_forecast_model_name = r.get('remote','timeseries','info','forecast','new_current_model');


    const setting_name = r.get('remote','timeseries','info','anomaly','setting','name');

    function on_radio_switch(model_type,prediction_type){
        console.log("Picked: " + model_type);
        hat.conn.send('timeseries', {'action': 'model_change','type':prediction_type, 'model': model_type});
    }

    function change_button_color(model_type,prediction_type){
        const models = r.get('remote','timeseries','info',prediction_type, 'model_state','models');
        if (!models) return '';
        for (const [key, value] of Object.entries(models)) {
	    if (value.split(".").at(-1) === model_type )
		return 'border: 3px solid green;'
        }
        return '';
    }

    const generate_setting_inputs = function (prediction_type) {
	if (!r.get('remote','timeseries','info',prediction_type,'setting')) return;

	var cur_model_name = prediction_type === 'anomaly'? cur_anomaly_model_name:cur_forecast_model_name;

	var t = Object.entries(r.get('remote','timeseries','info',prediction_type,'setting'))
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
				 'action': 'setting_change','type':prediction_type,
				 [key]: e.target.value});
			    }
			}
		    }],
		]]
	       });

	 return ["div",t];
    }

    const generate_model_buttons = function (prediction_type) {
        if (!r.get('remote','timeseries','info',prediction_type,'supported_models')) return;

        const cur_model_name = prediction_type === 'anomaly' ? cur_anomaly_model_name : cur_forecast_model_name;

        const t = r.get('remote', 'timeseries', 'info', prediction_type, 'supported_models').map(function (value, index) {
            return [
                "button",
                {
                    props: {
                        disabled: cur_model_name === value  || value === 'linear' || value === 'Cluster',
                        type: 'checkbox', id: 'id1',
                        name: 'modelSelect',
                        style: change_button_color(value, prediction_type),
                        value: 'Forest'
                    },
                    on: {click: () => on_radio_switch(value, prediction_type)}
                },
                value
            ]
        });
        return ["div",t];
    }

    const generate_div = function (prediction_type){
        const cur_model_name = prediction_type === 'anomaly' ? cur_anomaly_model_name : cur_forecast_model_name;
        return ['div',
            {props: {
                    id: prediction_type + '_div',
                }},
            ["label",{props: {for: 'input2'}},' Current '+prediction_type+' Model '],
            ["input",{props: {disabled: true, id: 'input2',value: cur_model_name }}],
            ["br"],
            generate_setting_inputs(prediction_type),
            ["br"],
            ["label",{props: {for: prediction_type+'_buttons'}},prediction_type+' models: '],
            ['div',{props: {id: prediction_type+'_buttons'}},generate_model_buttons(prediction_type)]
        ];
    }

    return ['div.main',
        ['div.settings', generate_div('anomaly'), generate_div('forecast')],
        ['div.plot',
            {
                plotData: data,
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

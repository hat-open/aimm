//------------------------------------------------------------------------------
//---------------Functions for plotting -----------------------------------------
//------------------------------------------------------------------------------

import * as plotly from 'plotly.js/dist/plotly.js';


let layout = {
    title: 'Not defined yet',
    xaxis: {
        title: 'Time (seconds)',
        showgrid: true,
        zeroline: false
    },
    yaxis: {
        title: 'Value (units)',
        showline: false,
        range: [-15.00, 35.00]
    }
};

export function getGraph() {
    let graph;
    let graphRequest = r.get('graph');
    if (graphRequest === undefined)
        graph = '';
    else {
        let graphData;
        let asdu = graphRequest['id'];
        let type=graphRequest['type'];

        layout.title = type + " " + graphRequest['id'];
        
        if (type === 'res_line') asdu += 10;

        graphData = r.get('remote', 'adapter_database', type, "asdu_" + String(asdu));
        graph = plot(graphData, layout);
    }

    return graph;

}


export function plot(dataPoints, layout, config) {



    const _config = config ? config : {
        displayModeBar: true,
        responsive: true,
        staticPlot: true
    };
    const x_data = [];
    for (let i = 0; i < 20; i++) {
        x_data.push(i - 20);
    }

    const format_data = [];
    for (const [key, value] of Object.entries(dataPoints)) {
        format_data.push(
            {
                x: x_data,
                y: value,
                line: { shape: 'spline' },
                type: 'scatter',
                name: key

            });

    }

    return ['div.plot', {
        plotData: format_data,
        hook: {
            insert: vnode => plotly.newPlot(vnode.elm, format_data, layout, _config),
            update: (oldVnode, vnode) => {
                if (u.equals(oldVnode.data.plotData, vnode.data.plotData)) return;
                plotly.react(vnode.elm, format_data, layout, _config);
            },
            destroy: vnode => plotly.purge(vnode.elm)
        }
    }
    ];
}
import 'main/index.scss';
import {svgElem} from './svg.js';
import {getTrafTable,getLineTable,getBusTable,getSwitchTable} from './tables.js';
import {getGraph} from './graph.js';

export function vt() {

    //gets all HTML tables
    let busTable= new getBusTable();
    let lineTable=new getLineTable();
    let trafoTable=new getTrafTable();
    let switchTable=new getSwitchTable();

    //gets other graphic elements
    let svgElement=new svgElem();
    let graph=new getGraph();



    return ["div",
        {/* upper row  */
            'attrs': {
                'width': '100%',
                'height': '400'
            }
        },
        ["div", { props: { className: 'mainRow' } },

            ['table', { props: { className: 'statTable' } }, lineTable],
            ['div', { props: { className: 'svgContainer' } }, svgElement],
            ['table', { props: { className: 'statTable thinTable' } }, busTable],
            ['table', { props: { className: 'statTable thinTable' } }, trafoTable],
            ['table', { props: { className: 'statTable thinTable' } }, switchTable],
        ],
        ['div', { props: { className: 'plotRow' } },
            ['div.plotContainer', graph]
        ]
    ];
}
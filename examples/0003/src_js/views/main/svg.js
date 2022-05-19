//------------------------------------------------------------------------------
//---------------Functions that draw svg elements-------------------------------
//------------------------------------------------------------------------------

import {onHover} from './reaction.js';


//Main SVG function ,returns the whole image
export function svgElem() {

    let swValues=[];
    for (let i = 30; i < 38; i++) {

        let swValue = r.get('remote', 'adapter', String(i) + '+' + '0');
        swValues.push(swValue);
    }

    return ['svg',
        {
            'attrs': {
                'class': 'svg',
                'xmlns': 'http://www.w3.org/2000/svg',
                'viewBox':"0 0 800 400",
                'preserveAspectRatio':"xMidYMid meet"
            }
        },



        //YELLOW RECTANGLE
        ['rect'],

        //BUSES
        busImg(100, 200, 40, 0),
        busImg(190, 200, 40, 1),
        busImg(250, 200, 40, 2),
        busImg(390, 200, 40, 3),
        busImg(450, 200, 150, 4),
        busImg(630, 135, 50, 5),
        busImg(630, 265, 50, 6),

        //SWITCHES
        switchImg(190, 200, 0, swValues[0]),
        switchImg(390, 200, 1, swValues[1]),
        switchImg(450, 100, 2, swValues[2]),
        switchImg(450, 300, 3, swValues[3]),
        switchImg(510 + 60, 100, 4, swValues[4]),
        switchImg(510 + 60, 300, 5, swValues[5]),
        switchImg(510 + 60, 170, 6, swValues[6]),
        switchImg(510 + 60, 230, 7, swValues[7]),

        //TRAF
        trafoImg(190 + 60, 200),

        //GROUND
        _smallLineImg(190 + 60, 230, 30, 0),
        _smallLineImg(190 + 60 + 30, 230, 45, 90),
        shunt(190 + 60 + 25, 275, "Shunt"),
        groundImg(190 + 60 + 30, 300),


        //LINES
        lineImg(100, 200, 0, 90),
        lineImg(510, 300, 1, 60),
        lineImg(510, 100, 2, 60),
        lineRoundImg(510 + 40, 170, 210, 3),


        //GENERATORS & ARROWS
        generatorImg(630, 135),
        generatorImg(630, 230),
        outImg(630, 300, "Load", 60),
        outImg(100, 200, "External \ngrid", 60, false),

        //LEGEND
        legendImg(100, 300)

    ];
}  


//SMALL GRAPHIC ELEMENTS
//-----------------------------------------------------------
let _thickLineImg = function (right, down, len = 150) {
    return ['line#svg_4', {
        'attrs': {
            'stroke-width': '4',
            'stroke-linecap': 'undefined',
            'stroke-linejoin': 'undefined',
            'y2': String(down - len),
            'x2': String(right),
            'y1': String(down + len),
            'x1': String(right),
            'stroke': '#000',
            'fill': 'none'
        }

    }
    ]
};

let _smallLineImg = function (right, down, len = 20, angle = 0, strokeW = 1) {
    let rotationOffset = 0;
    if (angle !== 0 && angle < 90) {
        rotationOffset = len;
    }
    return ['line#svg_4', {
        'attrs': {
            'transform': 'rotate(' + String(angle) + ',' + String(right + rotationOffset) + "," + String(down) + ')',
            'stroke-width': String(strokeW),
            'stroke-linecap': 'undefined',
            'stroke-linejoin': 'undefined',
            'y2': String(down),
            'x2': String(right + len),
            'y1': String(down),
            'x1': String(right),
            'stroke': '#000',
            'fill': 'none'
        }
    }
    ]
};

let _circleImg = function (right, down, radius) {
    return ['ellipse#svg_15', {
        'attrs': {
            'ry': String(radius),
            'rx': String(radius),
            'cy': String(down),
            'cx': String(right),
            'stroke': '#000',
            'fill': 'none'
        }
    }]
};
let _rectImg = function (right, down, color) {
    return ['rect#svg_15', {
        'attrs': {
            'width': String(20),
            'height': String(20),
            'x': String(right),
            'y': String(down),
            'stroke': '#000',
            'fill': color
        }
    }]
};

let busImg = function (right, down, length, id = 0) {
    return ['g',
        {
            'attrs': {

            },

            on: {
                //click: () => trafoChange("Bus"),
                mouseover: () => {
                    onHover(right - 10, down - length - 30, 20, length * 2 * 1.4, 'bus', id);

                }



            }
        },
        _thickLineImg(right, down, length),
        _textImg(right - 15, down - (length > 50 ? 120 : 15), String(id)),
        //_textImg(right, down, 'Line')
    ]

};
let _textImg = function (right, down, text, color = 'black') {

    return [
        'text#svg_3', {
            'attrs': {
                'style': 'cursor: move;',
                'space': 'preserve',
                'text-anchor': 'start',
                'font-family': 'sans-serif',
                'font-size': '14',
                'stroke-width': '0',
                'y': String(down - 40),
                'x': String(right + 10),
                'fill': color

            },

        },
        text
    ]
}
let _arrowImg = function (right, down, len = 60, angle = 0, pointerSize = 10, lineWidth = 2) {

    return ['g',
        {
            'attrs': {
                'stroke-width': '2',
                'transform': 'rotate(' + angle + ', ' + String(right) + "," + String(down) + ')',
            }
        },

        _smallLineImg(right, down, len, 0, lineWidth),
        _smallLineImg(right + len - pointerSize, down, pointerSize, 30, lineWidth),
        _smallLineImg(right + len - pointerSize, down, pointerSize, - 30, lineWidth),
    ]
};


//MAIN GRAPHIC ELEMENTS
//-----------------------------------------------------------
let legendImg = function (right, down) {
    return ['g',
        {
            'attrs': {
                'stroke-width': '1'
            }
        },
        _rectImg(right, down, 'black'),
        _rectImg(right, down + 30, 'red'),
        _rectImg(right, down + 60, 'green'),
        _textImg(right + 20, down + 55, 'Bus ID'),
        _textImg(right + 20, down + 55 + 30, 'Line ID'),
        _textImg(right + 20, down + 55 + 60, 'Switch ID'),
    ]

};

let generatorImg = function (right, down) {
    return ['g',
        {
            'attrs': {
                'stroke-width': '1'
            }
        },
        _smallLineImg(right, down),
        _circleImg(right + 35, down, 15),
        _textImg(right + 20, down + 45, 'G'),
        _textImg(right + 45, down + 45, 'Generator')
    ]

};

let lineImg = function (right, down, id, length) {
    return ['g',
        {
            'attrs': {
                'stroke-width': '2'
            },
            on: {
                //click: () => trafoChange("Line"),
                mouseover: () => {
                    onHover(right - 10, down - 25, length * 1.2, 50, 'line', id);

                }



            }
        },
        _arrowImg(right, down, length),
        _textImg(right + 0.6 * length / 2, down + 30, String(id), 'red'),
        _textImg(right + 0.4 * length / 2, down + 60, 'Line')
    ]

};

let outImg = function (right, down, text, length, dirRight = true) {
    return ['g',
        {
            'attrs': {
                'stroke-width': '2'
            }
        },
        _arrowImg(right, down, 60, dirRight ? 0 : 180, 15, 1),
        _textImg(right + (dirRight ? 30 : -100), down + 60, text)
    ]

};

let shunt = function (right, down, text) {
    return ['g',

        _smallLineImg(right, down, 10, 0, 1),
        _smallLineImg(right, down, 25, 90, 1),
        _smallLineImg(right + 10, down, 25, 90, 1),
        _smallLineImg(right, down + 25, 10, 0, 1),
        _circleImg(right + 5, down + 8, 2),
        _circleImg(right + 5, down + 17, 2),
        _textImg(right + 5, down + 55, text)
    ]

};

let trafoImg = function (right, down) {
    return ['g',
        {
            'attrs': {
                'stroke-width': '1'
            },
            on: {
                //click: () => onClick(right + 10, down - 60, 120, 100, 'trafo', 0),
                mouseover: () => {
                    onHover(right + 10, down - 60, 120, 100, 'trafo', 0);

                }
            }
        },
        _smallLineImg(right, down),
        _circleImg(right + 50, down, 30),
        _circleImg(right + 90, down, 30),
        _smallLineImg(right + 120, down),
        _textImg(right + 40, down, 'Trafo')
    ]
}

let switchImg = function (right, down, id = 99, switchOn = true) {

    return ['g',
        {
            'attrs': {
                'stroke-width': '1'
            },
            on: {
                //click: () => trafoChange("Switch"),
                mouseover: () => {
                    onHover(right + 10, down - 25, 40, 40, 'switch', id, switchOn);
                }



            }
        },

        _textImg(right + 15, down + 30, String(id), 'green'),



        ['line#svg_20', {
            'attrs': {
                'transform': 'rotate(' + (switchOn ? '-2' : '-30') + ', ' + String(right + 20) + "," + String(down) + ')',
                'stroke-linecap': 'undefined',
                'stroke-linejoin': 'undefined',
                'y2': String(down),
                'x2': String(right + 40),
                'y1': String(down),
                'x1': String(right + 20),
                'stroke': '#000',
                'fill': 'none'
            }
        }],
        ['line#svg_21', {
            'attrs': {
                'stroke-linecap': 'undefined',
                'stroke-linejoin': 'undefined',
                'y2': String(down),
                'x2': String(right + 20),
                'y1': String(down),
                'x1': String(right),
                'stroke': '#000',
                'fill': 'none'
            }
        }],
        ['line#svg_22', {
            'attrs': {
                'stroke-linecap': 'undefined',
                'stroke-linejoin': 'undefined',
                'y2': String(down),
                'x2': String(right + 60),
                'y1': String(down),
                'x1': String(right + 40),
                'stroke': '#000',
                'fill': 'none'
            }
        }]
    ]
};
let groundImg = function (right, down) {

    return ['g',
        {
            'attrs': {
                'stroke-width': '1'
            }
        },

        _smallLineImg(right, down, 20, 90),
        _smallLineImg(right - 30, down + 20, 30), _smallLineImg(right, down + 20, 30),
        _smallLineImg(right - 20, down + 25, 20), _smallLineImg(right, down + 25, 20),
        _smallLineImg(right - 10, down + 30, 10), _smallLineImg(right, down + 30, 10)

    ]
};

let lineRoundImg = function (right, down1, down2, id = 99) {

    return ['g',
        {
            'attrs': {
                'stroke-width': '1'
            },
            on: {
                //click: () => trafoChange("Switch"),
                mouseover: () => {
                    onHover(right - 25, down1 - 10, 50, 80, 'line', id);
                }

            }
        },
        _textImg(right - 30, down1 + 70, String(id), 'red'),
        _smallLineImg(right, down1, 20, 0, 3),
        _smallLineImg(right, down1, down2 - down1 + 20, 90, 3),
        _arrowImg(right, down2 + 20, 20, 0, 7)



    ]
};

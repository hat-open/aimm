//------------------------------------------------------------------------------
//------------------------On hover/click functions------------------------------
//------------------------------------------------------------------------------

export function triggerSwitch(asdu, value) {
    console.log("sending switch " + asdu + "," + value);

    hat.conn.send('adapter', { 'asdu': asdu, 'value': value });
}

export function onHover(right, down, size1, size2, type = 'undef', id = 99, value = null) {


    let bus;
    const elms = document.getElementsByClassName('tableElem');
    for (let i = 0; i < elms.length; i++) {
        elms[i].setAttribute('style', '');
    }


    drawRect(size1, size2, right, down, 'yellow', id, value, type);



    //fills cells in yellow ,depending on hovered element in svg

    if (type === 'bus') {
        bus = document.getElementById(id + '+' + 0);
        bus.setAttribute('style', 'background-color:yellow');
        bus = document.getElementById(id + '+' + 1);
        bus.setAttribute('style', 'background-color:yellow');
    }
    else if (type === 'switch') {

        bus = document.getElementById((id + 30) + '+' + 0);
        bus.setAttribute('style', 'background-color:yellow');


    } else if (type === 'line') {
        bus = document.getElementById((id + 10) + '+' + 0);
        bus.setAttribute('style', 'background-color:yellow');
        bus = document.getElementById((id + 10) + '+' + 1);
        bus.setAttribute('style', 'background-color:yellow');
        bus = document.getElementById((id + 10) + '+' + 2);
        bus.setAttribute('style', 'background-color:yellow');
        bus = document.getElementById((id + 10) + '+' + 3);
        bus.setAttribute('style', 'background-color:yellow');
        bus = document.getElementById((id + 10) + '+' + 4);
        bus.setAttribute('style', 'background-color:yellow');
    } else if (type === 'trafo') {


        bus = document.getElementById((20) + '+' + 0);
        bus.setAttribute('style', 'background-color:yellow');
        bus = document.getElementById((20) + '+' + 1);
        bus.setAttribute('style', 'background-color:yellow');
        bus = document.getElementById((20) + '+' + 2);
        bus.setAttribute('style', 'background-color:yellow');
        bus = document.getElementById((20) + '+' + 3);
        bus.setAttribute('style', 'background-color:yellow');
        bus = document.getElementById((20) + '+' + 4);
        bus.setAttribute('style', 'background-color:yellow');

    }
}

//draws a yellow rectangle on SVG dynamically on hover
function drawRect(size1, size2, right, down, color, id, value, type) {
    const rect = document.getElementsByTagName('rect')[0];


    rect.setAttribute('width', size1);
    rect.setAttribute('height', size2);

    rect.setAttribute('x', String(right));
    rect.setAttribute('y', String(down));
    rect.setAttribute('stroke', '#000');
    rect.setAttribute('fill', 'yellow');
    rect.setAttribute('fill-opacity', '30%');

    

    if (type === 'switch')
        rect.onclick = function () { triggerSwitch(id + 30, value) };
    else {
        rect.onclick = function () { graphAction(type, id) };
    }
}

function graphAction(type, id) {
    
    if (type === 'trafo') {
        r.set(['graph', 'type'], 'res_trafo');
        r.set(['graph', 'id'], 20);
    }

    else if (type === 'line') {
        r.set(['graph', 'type'], 'res_line');
        r.set(['graph', 'id'], id);
    }
    else if (type === 'bus') {
        r.set(['graph', 'type'], 'res_bus');
        r.set(['graph', 'id'], id);
    }

    else
        r.set(['graph'], undefined);




}
//------------------------------------------------------------------------------
//------------------------Table receive and draw functions----------------------
//------------------------------------------------------------------------------

import {triggerSwitch} from './reaction.js';


export function getSwitchTable() {
    const switches = [];
    let swTitles;

    swTitles = ['tr', [['th', '#'], ['th', 'Value'], ['th', '']]]

    for (let i = 30; i < 38; i++) {

        let swValue = r.get('remote', 'adapter', String(i) + '+' + '0');


        let swRow = [];
        swRow.push(['td', String(i)]);
        swRow.push(['td', { props: { className: 'tableElem', id: String(i) + '+' + '0' } }, String(swValue)]);
        swRow.push(['td', ['button', { on: { click: () => triggerSwitch(i, swValue) } }, 'SW']]);

        swRow = ['tr', swRow];
        switches.push(swRow);


    }
    return [swTitles, switches];

}
export function getBusTable() {
    const bus = [];

    bus.push(['tr', [['th', '#'], ['th', ' MW'], ['th', 'MVar']]]);
    for (let i = 0; i < 7; i++) {
        const busRow = [];
        busRow.push(['td', { props: { className: 'tableElem' } }, 'Bus:' + String(i)]);
        busRow.push(['td', { props: { className: 'tableElem', id: String(i) + '+' + '0' } }, `${r.get('remote', 'adapter', String(i) + '+' + '0')}`]);
        busRow.push(['td', { props: { className: 'tableElem', id: String(i) + '+' + '1' } }, `${r.get('remote', 'adapter', String(i) + '+' + '1')}`]);

        bus.push(['tr', busRow]);

    }

    return bus;

}

export function getTrafTable() {
    const trafNames = [' MW (high)', ' MVar (high)', ' MW (low)', ' MVar (low)', '% (overload)'];
    const traf = [];
    const trafHeader = ['tr', [['th', 'Traf 20'], ['th', 'Value']]];

    for (let i = 0; i <= 4; i++) {
        let trafTr = [];
        trafTr.push(['td', trafNames[i]])
        trafTr.push(['td', { props: { className: 'tableElem', id: String(20) + '+' + String(i) } }, `${r.get('remote', 'adapter', String(20) + '+' + String(i))}`]);
        trafTr = ['tr', trafTr];

        traf.push(trafTr);
    }

    return [trafHeader, traf];

}

export function getLineTable() {
    const line = [];
    let lineTitles;
    // const lineNames = [' MW (start)', ' MVar (start)', ' MW (end)', ' MVar (end)', '% (overload)'];

    lineTitles = ['tr', [['th', '#'], ['th', ' MW (start)'], ['th', ' MVar (start)'], ['th', ' MW (end)'], ['th', ' MVar (end)'], ['th', '', '% (overload)']]]

    line.push(lineTitles);


    for (let i = 10; i < 14; i++) {
        const lineRow = [['td', 'Line ' + String(i - 10)]];
        for (let j = 0; j < 5; j++) {
            lineRow.push(['td', { props: { className: 'tableElem', id: String(i) + '+' + String(j) } }, `${r.get('remote', 'adapter', String(i) + '+' + String(j))}`]);

        }
        line.push(['tr', lineRow])
    }

    return line;

}
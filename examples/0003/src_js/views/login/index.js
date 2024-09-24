export function vt() {
    return ['div.login', 'Loading...'];
}


export function init() {
    setTimeout(() => {
        hat.conn._conn.send({
            type: 'login',
            name: 'user',
            password: 'pass'
        });
    }, 0);
}

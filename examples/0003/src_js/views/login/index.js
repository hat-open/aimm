export function vt() {
    return ['div.login', 'Loading...'];
}


export function init() {
    setTimeout(() => {
        // TODO replace with hat.conn.login This is a fix to bypass login
        // function hashing that does not work when not secure connection
        // HTTP (not HTTPS).
        hat.conn._conn.send({
            type: 'login',
            name: 'user1',
            password: 'pass1'
        });
    }, 0);
}

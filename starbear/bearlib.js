
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;


function reScript(node){
    let script  = document.createElement("script");
    script.text = node.innerHTML;
    for (let attr of node.attributes) {
        script.setAttribute(attr.name, attr.value);
    }
    return script;
}


function activateScripts(node) {
    for (let child of node.querySelectorAll("script")) {
        child.parentNode.replaceChild(reScript(child), child);
    }
}


function incorporate(target, template, method, params) {
    let children = Array.from(template.childNodes);

    if (method === "innerHTML") {
        target.innerHTML = "";
        target.append(...children);
    }
    else if (method === "outerHTML") {
        target.replaceWith(...children);
    }
    else if (method === "beforebegin") {
        target.before(...children);
    }
    else if (method === "afterbegin") {
        target.prepend(...children);
    }
    else if (method === "beforeend") {
        target.append(...children);
    }
    else if (method === "afterend") {
        target.after(...children);
    }
    else {
        console.log(`Unknown HTML incorporation method: ${method}`);
    }
}


let commands = {
    put(params) {
        const template = document.createElement("div");
        template.innerHTML = params.content;
        activateScripts(template);
        const targets = document.querySelectorAll(params.selector);
        for (let target of targets) {
            incorporate(target, template, params.method, params);
        }
    },

    eval(params) {
        const context = params.selector && document.querySelector(params.selector);
        const func = (
            params.async
            ? new AsyncFunction(params.code)
            : new Function(params.code)
        );
        func.call(context);
    }
}


class Socket {
    constructor(path) {
        const protocol = location.protocol.match(/^https/) ? "wss" : "ws";
        this.url = `${protocol}://${location.host}${path}`;
        this.connectionCount = 0;
        this.socket = null;
        this.tries = 0;
    }

    send(obj) {
        this.socket.send(JSON.stringify(obj));
    }

    connect() {
        this.connectionCount++;
        this.socket = new WebSocket(this.url);
        this.socket.onopen = this.onopen.bind(this);
        this.socket.onmessage = this.onmessage.bind(this);
        this.socket.onclose = this.onclose.bind(this);
        this.socket.onerror = this.onerror.bind(this);
    }

    scheduleReconnect() {
        const delay = (2 ** this.tries) * 100;
        setTimeout(
            () => {
                this.connect();
            },
            delay,
        )
    }

    onopen() {
        this.tries = 0;
        this.send({type: "start", number: this.connectionCount});
    }

    onmessage(event) {
        let data = JSON.parse(event.data);
        let method = commands[data.command];
        if (method !== undefined) {
            method(data);
        }
        else {
            console.log(`[socket] Cannot parse message: ${data}`);
        }
    }

    onclose(event) {
        if (event.wasClean) {
            if (event.code === 3001) {
                // Application is done
            }
            else if (event.code === 3002) {
                // Application does not exist
                console.error(`[socket] Application does not exist.`);
            }
            else {
                console.log(`[socket] Connection closed (code=${event.code} reason=${event.reason || 'n/a'})`);
            }
        } else {
            console.error(`[socket] Connection died (code=${event.code})`);
            this.tries++;
            this.scheduleReconnect();
        }
    }

    onerror(error) {
        console.error(`[socket] Error: ${error}`);
    }
}


export function connect(path) {
    let sock = new Socket(path);
    sock.connect();
}

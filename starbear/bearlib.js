

///////////////
// Constants //
///////////////


const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;

const bearlibErrorCSS = new CSSStyleSheet();

bearlibErrorCSS.replaceSync(`
#starbear-error:empty {
    display: none;
}
#starbear-error {
    position: absolute;
    right: 0;
    top: 0;
    border: 2px solid red;
    padding: 3px;
    max-height: 300px;
    max-width: 90vw;
    overflow: scroll;
    white-space: pre;
    color: black;
    background: white;
}
`)

document.adoptedStyleSheets = [...document.adoptedStyleSheets, bearlibErrorCSS];


/////////////
// Globals //
/////////////


var $_autoid = 0


///////////////////////////////////
// Modifications to base classes //
///////////////////////////////////


HTMLElement.prototype.toJSON = function () {
    if (!this.id) {
        $_autoid++;
        this.id = `$$AUTOID${$_autoid}`
    }
    return {
        "%": "HTMLElement",
        selector: `#${this.id}`
    }
}


Event.prototype.toJSON = function () {
    return {
        "%": "Event",
        data: {
            type: this.type,
            inputType: this.inputType,
            button: this.button,
            buttons: this.buttons,
            shiftKey: this.shiftKey,
            altKey: this.altKey,
            ctrlKey: this.ctrlKey,
            metaKey: this.metaKey,
            key: this.key,
            target: this.target,
            form: this.target.elements && (new FormData(this)),
            value: this.target.value,
            refs: this.$refs,
        }
    }
}


class FormData {
    constructor(event) {
        let element = event.target;
        while (!(element.tagName === "FORM") && (element = element.parentNode)) {
        }
        this.target = element;
        this.submit = (event && event.type == "submit");
        this.refs = event.$refs;
        this.data = {};

        if (element) {
            const form = element.elements;
            for (let [k, v] of Object.entries(form)) {
                if (isNaN(k)) {
                    // Non-numeric key
                    this.data[k] = v.type === "checkbox" ? v.checked : v.value;
                }
                else if (v.name) {
                    let name = v.name;
                    v = form[v.name];
                    this.data[name] = v.type === "checkbox" ? v.checked : v.value;
                }
            }
        }
    }

    toJSON() {
        console.log(this);
        return {
            "%": "FormData",
            "data": this.data,
            "target": this.target,
            "submit": this.submit,
            "refs": this.refs,
        }
    }
}


///////////////
// Utilities //
///////////////


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


function hookOnloads(node, sock) {
    for (let child of node.querySelectorAll("link,script")) {
        let token = ++$_autoid;
        let wake = () => sock.wake(token);
        sock.requireWait(token);
        child.onload = wake;
        child.onerror = wake;
        setTimeout(wake, 250);  // Safety valve
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


//////////////////////////////
// Socket-received commands //
//////////////////////////////


let commands = {
    put(sock, params) {
        const template = document.createElement("div");
        template.innerHTML = params.content;
        activateScripts(template);
        if (params.add_onload_hooks) {
            hookOnloads(template, sock);
        }
        const targets = document.querySelectorAll(params.selector);
        for (let target of targets) {
            incorporate(target, template, params.method, params);
        }
    },

    resource(sock, params) {
        params.selector = "head";
        params.method = params.method || "beforeend";
        params.add_onload_hooks = true;
        commands.put(sock, params);
    },

    eval(sock, params) {
        const context = params.selector && document.querySelector(params.selector);
        const func = (
            params.async
            ? new AsyncFunction(params.code)
            : new Function(params.code)
        );
        func.call(context);
    },

    reload(sock, params) {
        window.location.reload();
    }
}


class Socket {
    constructor(path) {
        const protocol = location.protocol.match(/^https/) ? "wss" : "ws";
        this.url = `${protocol}://${location.host}${path}`;
        this.connectionCount = 0;
        this.socket = null;
        this.tries = 0;
        this.queue = [];
        this.waitPromise = null;
        this.waitReasons = [];
        this.errorDiv = document.createElement("div");
        this.errorDiv.id = ["starbear-error"]
        document.body.appendChild(this.errorDiv);
        this.loop();
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

    requireWait(token) {
        if (this.waitPromise === null) {
            this.waitPromise = new Promise(
                (resolve, reject) => {
                    this._resolve = resolve;
                    this._reject = reject;
                }
            )
            this.waitReasons = [];
        }
        this.waitReasons.push(token);
    }

    wake(token) {
        if (this.waitPromise !== null) {
            let idx = this.waitReasons.indexOf(token);
            if (idx !== -1) {
                this.waitReasons.splice(idx, 1);
            }
            if (this.waitReasons.length === 0) {
                this._resolve(null);
            }
        }
    }

    async loop() {
        while (true) {
            if (this.waitPromise !== null) {
                await this.waitPromise;
                this.waitPromise = null;
            }
            if (this.queue.length > 0) {
                let entry = this.queue.shift();
                let method = commands[entry.command];
                if (method !== undefined) {
                    method(this, entry);
                }
                else {
                    console.log(`[socket] Cannot parse message: ${entry}`);
                }
            }
            else {
                this.requireWait("messages");
            }
        }
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

    error(errorText) {
        this.errorDiv.innerHTML = `<div id="starbear-connection-error">${errorText}</div>`;
    }

    onopen() {
        this.tries = 0;
        this.send({type: "start", number: this.connectionCount});
        this.errorDiv.querySelector("#starbear-connection-error")?.remove();
    }

    onmessage(event) {
        let data = JSON.parse(event.data);
        if (!Array.isArray(data)) {
            data = [data];
        }
        this.queue.push(...data);
        this.wake("messages");
    }

    onclose(event) {
        if (event.wasClean) {
            if (event.code === 3001) {
                // Application is done
            }
            else if (event.code === 3002) {
                // Application does not exist
                console.error(`[socket] Application does not exist.`);
                this.error("Session killed. Please refresh.");
            }
            else {
                console.log(`[socket] Connection closed (code=${event.code} reason=${event.reason || 'n/a'})`);
            }
        } else {
            console.error(`[socket] Connection died (code=${event.code})`);
            this.error("Connection lost. Trying to reconnect...");
            this.tries++;
            this.scheduleReconnect();
        }
    }

    onerror(error) {
        console.error(`[socket] Error: ${error}`);
    }
}


////////////////////
// Starbear class //
////////////////////


class BearPromise {
    constructor(bear, reqid) {
        this.route = bear.route;
        this.reqid = reqid;
    }

    async post(data) {
        return await fetch(`${this.route}/post`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
    }

    async resolve(value) {
        try {
            return await this.post({
                reqid: this.reqid,
                value: value,
            })
        }
        catch (exc) {
            return await self.reject(exc);
        }
    }

    async reject(exc) {
        let message = `${exc.type}: ${exc.message}`;
        return await this.post({
            reqid: this.reqid,
            error: message,
        })
    }
}


class LocalPromise {
    constructor() {
        this.id = ++$_autoid;
        this.promise = new Promise(
            (resolve, reject) => {
                this.resolve = resolve;
                this.reject = reject;
            }
        );
    }

    toJSON() {
        return {"%": "Promise", id: this.id};
    }
}


class RemoteReference {
    constructor(id) {
        this.id = id;
    }

    toJSON() {
        return {"%": "Reference", id: this.id}
    }
}


export class Starbear {
    constructor(route) {
        this.route = route;
        this.socket = new Socket(`${this.route}/socket`);
        this.timers = {};
        this.localPromises = {};
        this.promise = reqid => new BearPromise(this, reqid);
    }

    connect() {
        this.socket.connect();
    }

    func(id) {
        return async (...args) => {
            return await fetch(`${this.route}/method/${id}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(args),
            })
        }
    }

    ref(id) {
        return new RemoteReference(id);
    }

    async cb(selector, extractor, promise) {
        let root = window;

        if (selector) {
            root = document.querySelector(selector);
            if (root.__object) {
                root = (await (root.__object));
            }
        }

        if (promise) {
            try {
                let result = await extractor.call(root);
                await promise.resolve(result);
            }
            catch (exc) {
                await promise.reject(exc);
                throw exc;
            }
        }
        else {
            extractor.call(root);
        }
    }

    resolveLocalPromise(pid, value) {
        let promise = this.localPromises[pid];
        this.localPromises[pid] = undefined;
        promise.resolve(value);
    }

    queue(id, feedback = false) {
        return async value => {
            let qvalue = value
            let promise = null;
            if (feedback) {
                promise = new LocalPromise();
                this.localPromises[promise.id] = promise;
                qvalue = [value, promise];
            }
            let response = await fetch(`${this.route}/queue`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    reqid: id,
                    value: qvalue,
                })
            })
            if (feedback) {
                return await promise.promise;
            }
            else {
                return response;
            }
        }
    }

    event(func) {
        let evt = window.event;
        evt.preventDefault();
        evt.stopPropagation();
        func.call(this, evt);
    }

    toggle(element, toggle, value = null) {
        let not_toggle = `not-${toggle}`
        let hasyes = e => e.classList.contains(toggle);
        let hasno = e => e.classList.contains(not_toggle);
        let hasit = e => hasyes(e) || hasno(e);

        let current = element;
        while (!hasit(current) && (current = current.parentNode)) {
        }
        if (!current) {
            return;
        }
        else {
            if (value === null) {
                current.classList.toggle(toggle);
                current.classList.toggle(not_toggle);
            }
            else if (value) {
                current.classList.add(toggle);
                current.classList.remove(not_toggle);
            }
            else {
                current.classList.remove(toggle);
                current.classList.add(not_toggle);
            }
        }
    }

    wrap(func, options) {
        const id = options.id;
        const bear = this;
        const timers = this.timers;

        function debounce(f, timeout) {
            return function (...args) {
                clearTimeout(timers[id]);
                timers[id] = setTimeout(
                    () => { f.call(this, ...args); },
                    timeout,
                );
            };
        }

        function nodebounce(f) {
            return function (...args) {
                clearTimeout(timers[id]);
                return f.call(this, ...args);
            };
        }

        function extract(f, extractors) {
            return function (arg) {
                const args = [];
                for (const extractor of extractors) {
                    let value = arg;
                    for (const part of extractor) {
                        value = value[part];
                    }
                    args.push(value);
                }
                return f.call(this, ...args);
            }
        }

        function getform(f) {
            return function (event) {
                // TODO: proper error when this is not an event
                return f.call(this, new FormData(event));
            }
        }

        function getrefs(f) {
            return function (event) {
                // TODO: proper error when this is not an event
                let element = event.target;
                let refs = [];
                do {
                    if (element.hasAttribute("--ref")) {
                        let lnk = element.getAttribute("--ref");
                        if (lnk.startsWith("obj#")) {
                            let [_, id] = lnk.split("#");
                            lnk = {"%": "Reference", "id": Number(id)};
                        }
                        refs.push(lnk);
                    }
                } while ((element = element.parentNode) instanceof Element);
                if (refs.length > 0) {
                    event.$refs = refs;
                    return f.call(this, event);
                }
            }
        }

        function part(f, pre_args) {
            return function (...post_args) {
                return f.call(this, ...pre_args, ...post_args)
            }
        }

        function pack(f) {
            return function (...args) {
                return f.call(this, args)
            }
        }

        function prepost(f, pre, post) {
            return async function (...args) {
                for (let pre_f of pre) {
                    pre_f.call(this);
                }
                let result = f.call(this, ...args);
                if (result instanceof Promise) {
                    result = await result;
                }
                for (let post_f of post) {
                    post_f.call(this, result);
                }
            }
        }

        function run_toggles(f, toggles) {
            function pre() {
                for (let toggle of toggles) {
                    bear.toggle(this, toggle, true);
                }
            }
            function post(_) {
                for (let toggle of toggles) {
                    bear.toggle(this, toggle, false);
                }
            }
            return prepost(f, [pre], [post]);
        }

        if (options.pack) {
            func = pack(func);
        }
        if (options.partial) {
            func = part(func, options.partial);
        }
        if (options.extract) {
            let extractors = options.extract;
            if (typeof extractors === 'string') {
                extractors = [extractors];
            }
            extractors = extractors.map(x => x.split("."));
            func = extract(func, extractors);
        }
        if (options.form) {
            func = getform(func);
        }
        if (options.refs) {
            func = getrefs(func);
        }
        if (options.toggles) {
            let toggles = (
                (typeof options.toggles === "string")
                ? [options.toggles]
                : options.toggles
            );
            func = run_toggles(func, toggles);
        }
        if (options.pre || options.post) {
            func = prepost(func, options.pre || [], options.post || []);
        }
        if (options.debounce) {
            func = debounce(func, options.debounce * 1000);
        }
        else {
            func = nodebounce(func);
        }
        return func;
    }
}


var $_autoid = 0
var $$_BEAR_TIMERS = {};
var $$_BEAR_LOCAL_PROMISES = {};


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


HTMLFormControlsCollection.prototype.toJSON = function (event) {
    const results = {};
    for (let [k, v] of Object.entries(this)) {
        if (isNaN(k)) {
            // Non-numeric key
            results[k] = v.type === "checkbox" ? v.checked : v.value;
        }
        else if (v.name) {
            let name = v.name;
            v = this[v.name];
            results[name] = v.type === "checkbox" ? v.checked : v.value;
        }
    }
    event = event || window.event
    results.$submit = (event && event.type == "submit");
    return results;
}


Event.prototype.toJSON = function () {
    return {
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
        form: this.target.elements,
        value: this.target.value,
    }
}


function $$BEAR_FUNC(id) {
    return async (...args) => {
        return await fetch(`${BEAR_ROUTE}/method/${id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(args),
        })
    }
}


async function $$BEAR_CB(selector, extractor, promise) {
    let root = window;

    if (selector) {
        root = document.querySelector(selector);
        if (root.__object) {
            root = (await (root.__object));
        }
    }

    if (promise) {
        try {
            let result = await extractor(root);
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


class $$BEAR_PROMISE {
    constructor(reqid) {
        this.reqid = reqid;
    }

    async post(data) {
        return await fetch(`${BEAR_ROUTE}/post`, {
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


class $$BEAR_LOCAL_PROMISE {
    constructor() {
        this.id = ++$_autoid;
        this.promise = new Promise(
            (resolve, reject) => {
                this.resolve = resolve;
                this.reject = reject;
            }
        );
        $$_BEAR_LOCAL_PROMISES[this.id] = this;
    }

    toJSON() {
        return {"%": "Promise", id: this.id};
    }
}


function $$BEAR_RESOLVE_LOCAL_PROMISE(pid, value) {
    let promise = $$_BEAR_LOCAL_PROMISES[pid];
    $$_BEAR_LOCAL_PROMISES[pid] = undefined;
    promise.resolve(value);
}


function $$BEAR_QUEUE(id, feedback = false) {
    return async value => {
        let qvalue = value
        let promise = null;
        if (feedback) {
            promise = new $$BEAR_LOCAL_PROMISE();
            qvalue = [value, promise];
        }
        let response = await fetch(`${BEAR_ROUTE}/queue`, {
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


function $$BEAR_EVENT(func) {
    let evt = window.event;
    evt.preventDefault();
    evt.stopPropagation();
    func.call(this, evt);
}


function $$BEAR_TOGGLE(element, toggle, value = null) {
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


function $$BEAR_WRAP(func, options) {
    const id = options.id;

    function debounce(f, timeout) {
        return function (...args) {
            clearTimeout($$_BEAR_TIMERS[id]);
            $$_BEAR_TIMERS[id] = setTimeout(
                () => { f.call(this, ...args); },
                timeout,
            );
        };
    }

    function nodebounce(f) {
        return function (...args) {
            clearTimeout($$_BEAR_TIMERS[id]);
            f.call(this, ...args);
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
            let element = event.target;
            while (!(element.tagName === "FORM") && (element = element.parentNode)) {
            }
            const form = element ? element.elements.toJSON(event) : {};
            form.$target = element.toJSON();
            return f.call(this, form);
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
                $$BEAR_TOGGLE(this, toggle, true);
            }
        }
        function post(_) {
            for (let toggle of toggles) {
                $$BEAR_TOGGLE(this, toggle, false);
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

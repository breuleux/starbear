
var $_autoid = 0


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
            results[k] = v.type === "checkbox" ? v.checked : v.value;
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


function $$BEAR_QUEUE(id) {
    return async value => {
        return await fetch(`${BEAR_ROUTE}/queue`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                reqid: id,
                value: value,
            })
        })
    }
}


function $$BEAR_EVENT(func) {
    let evt = window.event;
    evt.preventDefault();
    evt.stopPropagation();
    func(evt);
}


$$_BEAR_TIMERS = {};


function $$BEAR_WRAP(func, options) {
    const id = options.id;

    function debounce(f, timeout) {
        return (...args) => {
            clearTimeout($$_BEAR_TIMERS[id]);
            $$_BEAR_TIMERS[id] = setTimeout(
                () => { f(...args); },
                timeout,
            );
        };
    }

    function nodebounce(f) {
        return (...args) => {
            clearTimeout($$_BEAR_TIMERS[id]);
            f(...args);
        };
    }

    function extract(f, extractors) {
        return arg => {
            const args = [];
            for (const extractor of extractors) {
                let value = arg;
                for (const part of extractor) {
                    value = value[part];
                }
                args.push(value);
            }
            return f(...args);
        }
    }

    function getform(f) {
        return event => {
            // TODO: proper error when this is not an event
            let element = event.target;
            while (!(element.tagName === "FORM") && (element = element.parentNode)) {
            }
            const form = element ? element.elements.toJSON(event) : {};
            return f(form);
        }
    }

    function part(f, pre_args) {
        return (...post_args) => f(...pre_args, ...post_args)
    }

    function pack(f) {
        return (...args) => f(args)
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
    if (options.debounce) {
        func = debounce(func, options.debounce * 1000);
    }
    else {
        func = nodebounce(func);
    }
    return func;
}

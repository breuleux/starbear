
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


HTMLFormControlsCollection.prototype.toJSON = function () {
    const results = {};
    for (let [k, v] of Object.entries(this)) {
        if (isNaN(k)) {
            results[k] = v.type === "checkbox" ? v.checked : v.value;
        }
    }
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


async function $$BEAR_CB(selector, method, args, promise, return_result) {
    let object = window;
    if (selector) {
        const element = document.querySelector(selector);
        object = (await (element.__object));
    }
    try {
        let result = await object[method](...args);
        await promise.resolve(return_result ? result : null);
    }
    catch (exc) {
        await promise.reject(exc);
        throw exc;
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


function $$BEAR_QUEUE(id, tag) {
    return async (...args) => {
        return await fetch(`${BEAR_ROUTE}/queue`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                reqid: id,
                value: args,
                tag: tag,
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

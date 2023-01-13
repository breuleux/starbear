
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


function $$BEAR(id, ...args) {
    const exec = $$BEAR_FUNC(id);
    const execNow = async () => {
        try {
            await exec({
                type: evt.type,
                button: evt.button,
                shiftKey: evt.shiftKey,
                altKey: evt.altKey,
                ctrlKey: evt.ctrlKey,
                metaKey: evt.metaKey,
                key: evt.key,
                offsetX: evt.offsetX,
                offsetY: evt.offsetY,
            });
        }
        catch(exc) {
            let message = `${exc.type}: ${exc.message}`;
            throw exc;
        }
    }

    let evt = window.event;

    if (evt === undefined || evt.type === "load") {
        // If not in an event handler, we return the execution
        // function directly
        return exec;
    }
    else {
        // The call is in an event handler like onclick, for example
        // <div onclick="$$BEAR(15)">...</div>, so we execute it
        // immediately.
        evt.preventDefault();
        evt.stopPropagation();
        execNow();
    }
}


async function $$BEAR_CB(selector, method, args, promise) {
    let element = document.querySelector(selector);
    let object = element && element.__constructed;
    let result = object[method](...args);
    await promise.resolve(result);
}


class $$BEAR_PROMISE {
    constructor(reqid) {
        this.reqid = reqid;
    }

    async resolve(value) {
        return await fetch(`${BEAR_ROUTE}/post`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                reqid: this.reqid,
                value: value,
            })
        })
    }
}

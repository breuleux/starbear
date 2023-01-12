
function $$BEAR_FUNC(id) {
    return async (...args) => {
        let _resolve = null;
        let _reject = null;
        const response = new Promise(
            (resolve, reject) => {
                _resolve = resolve;
                _reject = reject;
            }
        );

        const req = new XMLHttpRequest();
        req.onreadystatechange = () => {
            if (req.readyState === 4) {
                if (req.status == 200) {
                    console.log(req);
                    _resolve(JSON.parse(req.responseText))
                }
            }
        };
        req.open("POST", `${BEAR_ROUTE}/method/${id}`, true);
        req.setRequestHeader('Content-type', 'application/json; charset=UTF-8');
        req.send(JSON.stringify(args));

        return await response;
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

function $$BEAR_CB(selector, method, args, callback) {
    let element = document.querySelector(selector);
    let object = element && element.__constructed;
    let result = object[method](...args);
    callback(result);
}

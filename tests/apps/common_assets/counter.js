
export default class Counter {
    constructor(options) {
        this.current = 0;
        this.increment = options.increment || 1;
        this.button = document.createElement("button");
        this.button.classList.add(options.cls || "counter");
        this.button.addEventListener("click", this.activate.bind(this));
        this.activate();
    }

    getElement() {
        return this.button;
    }

    activate() {
        this.button.innerText = this.current;
        this.current += this.increment;
    }
}

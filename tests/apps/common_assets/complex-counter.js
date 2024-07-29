
export default class ComplexCounter {
    constructor(options) {
        this.current = 0;
        this.increment = options.increment;
        this.button = document.createElement("button");
        this.button.classList.add(options.cls || "counter");
        this.button.addEventListener("click", this.activate.bind(this));
        this.activate();
    }

    getElement() {
        return this.button;
    }

    async activate() {
        this.button.innerText = this.current;
        this.current = await this.increment(this.current);
        console.log(this.increment);
        console.log(this.current);
    }
}

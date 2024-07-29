
import Counter from "./counter.js"

export default class FancyCounter extends Counter {
    constructor(options) {
        super(options);
        this.target = options.target;
        this.button.innerText = `Increment by ${this.increment}`;
        this.activate();
    }

    activate() {
        if (this.target) {
            this.target.innerText = this.current;
            this.current += this.increment;
        }
    }
}

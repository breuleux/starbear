import { editor, Range, KeyMod as KM, KeyCode as KC } from "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/+esm"

document.head.insertAdjacentHTML('beforeend', `<link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/vscode-codicons@0.0.17/dist/codicon.min.css">`);


let currId = 0;


editor.defineTheme(
    "nobg",
    {
        base: "vs",
        inherit: true,
        rules: [],
        colors: {
            "editor.background": "#00000000",
        }
    }
);


let optionDefaults = {
    sendDeltas: true,
    onChangeDebounce: 0.25,
    maxHeight: 0,
    firstLineno: false,
}


let editorDefaults = {
    lineNumbers: false,
    minimap: {enabled: false},
    scrollBeyondLastLine: false,
    overviewRulerLanes: 0,
    folding: false,
    automaticLayout: true,
}


export class Editor {
    constructor(options) {
        this.id = currId++;
        this.communicated = false;
        this.container = document.createElement("div");
        this.options = {...optionDefaults, ...options};
        this.options.editor = {
            ...editorDefaults,
            value: this.options.value,
            language: this.options.language,
            ...this.options.editor,
        };
        if (this.options.firstLineno !== false) {
            this.options.editor.lineNumbers = i => i + this.options.firstLineno - 1
        }

        this.setupElement();
        this.setupEditor();

        if (this.options.autofocus) {
            setTimeout(() => this.editor.focus(), 0);
        }
    }

    getElement() {
        return this.container;
    }

    setupElement() {
        this.container.classList.add("starbear-editor-area");
    }

    hasChanged() {
        return !this.communicated || this.changesLength === false || this.changesLength > 0;
    }

    packageContent() {
        const changes = this.changes;
        this.changes = undefined;
        const sendContent = !this.communicated || this.changesLength === false;
        this.changesLength = 0;
        return {
            "%": "MonacoEditor",
            id: this.id,
            content: sendContent ? this.editor.getValue() : null,
            delta: sendContent ? null : (changes || []),
        }
    }

    trigger(func=null, params=null) {
        clearTimeout(this._timer);
        if (this.options.onChange && this.hasChanged()) {
            this.options.onChange({
                content: this.packageContent(),
                event: "change",
            });
            this.communicated = true;
        }
        if (func) {
            let sel = this.editor.getSelection();
            params.content = this.packageContent();
            params.selection = [
                [sel.startLineNumber, sel.startColumn],
                [sel.endLineNumber, sel.endColumn]
            ];
            func(params);
            this.communicated = true;
        }
    }

    onChange(evt) {
        this.updateContextKeys();
        if (!this.options.sendDeltas) {
            this.changesLength = false;
        }
        else if (this.changes === undefined) {
            this.changes = [];
            this.changesLength = 0;
        }
        if (this.changesLength !== false) {
            for (let chg of evt.changes) {
                this.changes.push([chg.rangeOffset, chg.rangeLength, chg.text]);
                this.changesLength += 7 + chg.text.length;
                if (this.changesLength > this.editor.getModel().getValueLength()) {
                    this.changesLength = false;
                }
            }
        }
        const debounce = this.options.onChangeDebounce;
        if (debounce) {
            clearTimeout(this._timer);
            this._timer = setTimeout(this.trigger.bind(this), debounce * 1000);
        }
        else {
            this.trigger();
        }
    }

    event_updateHeight() {
        const contentHeight = Math.min(
            this.options.maxHeight || 500,
            this.editor.getContentHeight()
        );
        this.container.style.height = `${contentHeight}px`;
        // Normally the relayout should be automatic, but doing it here
        // avoids some flickering
        this.editor.layout({
            width: this.container.offsetWidth - 10,
            height: contentHeight
        });
    }

    updateContextKeys() {
        let {lineNumber, column} = this.editor.getPosition();
        let model = this.editor.getModel();
        let total = model.getLineCount();
        this.atBeginning.set(lineNumber == 1);
        this.atEnd.set(lineNumber == total);
        if (total > 1) {
            this.multiline.set(true);
        }
        else {
            let upToCursor = model.getValueInRange({
                startLineNumber: lineNumber,
                endLineNumber: lineNumber,
                startColumn: 0,
                endColumn: column,
            });
            this.multiline.set(
                upToCursor.match(/[\(\[\{:,]$|"""$|^@/)
            );
        }
    }

    setupEditor() {
        this.editor = editor.create(this.container, this.options.editor);

        this.atBeginning = this.editor.createContextKey("atBeginning", true);
        this.atEnd = this.editor.createContextKey("atEnd", true);
        this.multiline = this.editor.createContextKey("multiline", false);

        this.editor.onDidChangeCursorPosition(this.updateContextKeys.bind(this));

        if (this.options.onChange) {
            this.editor.getModel().onDidChangeContent(
                this.onChange.bind(this),
            )
        }

        for (let [key_cond, func] of Object.entries(this.options.bindings || ({}))) {
            let binding = 0;
            let [key, precondition = null] = key_cond.split(/ when /, 2);
            for (let part of key.split(/ *\+ */)) {
                binding = binding | (KM[part] || KC[part]);
            }
            this.editor.addAction({
                id: `binding-${key}`,
                label: `binding-${key}`,
                keybindings: [binding],
                run: this.trigger.bind(this, func, {event: "command", key: key}),
                precondition: precondition,
            });
        }

        let highlight = this.options.highlight?.line;
        if (highlight !== undefined) {
            highlight -= (this.options.firstLineno || 1) - 1;
            this.hl = [];
            this.hl = this.editor.deltaDecorations(this.hl, [
                {
                    range: new Range(highlight, 1, highlight, 1),
                    options: {
                        isWholeLine: true,
                        className: this.options.highlight.class_name,
                    },
                },
            ]);
            setTimeout(
                () => this.editor.revealLineInCenter(highlight),
                0,
            )
        }

        this.editor.onDidContentSizeChange(this.event_updateHeight.bind(this));
        this.event_updateHeight();
    }

    focus() {
        this.editor.focus();
    }

    set(text, focus = true, position = null) {
        this.editor.setValue(text);
        if (focus) {
            this.focus();
        }
        if (position === "start") {
            this.editor.setPosition({lineNumber: 1, column: 0});
        }
        else if (position === "endL1") {
            this.editor.setPosition({lineNumber: 1, column: 1000000});
        }
        else if (position === "end") {
            let nlines = this.editor.getModel().getLineCount();
            this.editor.setPosition({lineNumber: nlines, column: 1000000});
        }
    }

    insert(text, focus = true) {
        let selection = this.editor.getSelection();
        let op = {range: selection, text: text, forceMoveMarkers: true};
        this.editor.executeEdits("my-source", [op]);
        if (focus) {
            this.focus();
        }
    }
}


export function colorized(options) {
    const element = document.createElement("div");
    editor
    .colorize(options.text, options.language)
    .then(result => { element.innerHTML = result; });
    return element;
}

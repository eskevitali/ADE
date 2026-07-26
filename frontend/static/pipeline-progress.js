/**
 * Reusable pipeline progress bar for ADE workflows.
 */
class PipelineProgress {
  constructor(container, steps, options = {}) {
    this.container = typeof container === "string" ? document.getElementById(container) : container;
    this.steps = steps;
    this.options = { showSpinner: true, ...options };
    this.currentIndex = -1;
    this._render();
  }

  _render() {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="pipeline-progress rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="pipeline-label text-sm font-medium text-indigo-200">Ожидание…</span>
          <span class="pipeline-pct text-xs text-gray-500">0%</span>
        </div>
        <div class="h-2.5 bg-gray-800/80 rounded-full overflow-hidden mb-3">
          <div class="pipeline-bar h-full rounded-full bg-gradient-to-r from-indigo-600 to-indigo-400 transition-all duration-700 ease-out" style="width:0%"></div>
        </div>
        <div class="pipeline-steps flex flex-wrap gap-1.5"></div>
        ${this.options.showSpinner ? '<div class="pipeline-spinner mt-3 flex items-center gap-2 text-xs text-indigo-300/80 hidden"><span class="inline-block w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin"></span><span class="spinner-text">Обработка…</span></div>' : ""}
      </div>`;
    this.labelEl = this.container.querySelector(".pipeline-label");
    this.pctEl = this.container.querySelector(".pipeline-pct");
    this.barEl = this.container.querySelector(".pipeline-bar");
    this.stepsEl = this.container.querySelector(".pipeline-steps");
    this.spinnerEl = this.container.querySelector(".pipeline-spinner");
    this.spinnerTextEl = this.container.querySelector(".spinner-text");
    this._renderSteps();
  }

  _renderSteps() {
    if (!this.stepsEl) return;
    this.stepsEl.innerHTML = this.steps
      .map((s, i) => {
        const cls =
          i < this.currentIndex
            ? "bg-emerald-900/50 text-emerald-300 border-emerald-500/30"
            : i === this.currentIndex
              ? "bg-indigo-600/40 text-indigo-200 border-indigo-400/50 ring-1 ring-indigo-400/40"
              : "bg-gray-800/50 text-gray-500 border-gray-700/50";
        return `<span class="pipeline-step px-2 py-0.5 rounded-full text-[10px] border ${cls}" data-idx="${i}">${s.label}</span>`;
      })
      .join("");
  }

  setStep(index, label) {
    this.currentIndex = index;
    const pct = Math.round(((index + 1) / this.steps.length) * 100);
    if (this.barEl) this.barEl.style.width = `${pct}%`;
    if (this.pctEl) this.pctEl.textContent = `${pct}%`;
    if (this.labelEl) this.labelEl.textContent = label || this.steps[index]?.label || "Обработка…";
    this._renderSteps();
    this.setBusy(true, label);
  }

  setByKey(key, label) {
    const idx = this.steps.findIndex((s) => s.key === key);
    if (idx >= 0) this.setStep(idx, label);
  }

  setBusy(busy, text) {
    if (!this.spinnerEl) return;
    this.spinnerEl.classList.toggle("hidden", !busy);
    if (this.spinnerTextEl && text) this.spinnerTextEl.textContent = text;
  }

  complete(label) {
    this.currentIndex = this.steps.length - 1;
    if (this.barEl) this.barEl.style.width = "100%";
    if (this.pctEl) this.pctEl.textContent = "100%";
    if (this.labelEl) this.labelEl.textContent = label || "Готово";
    this._renderSteps();
    this.setBusy(false);
  }

  fail(label) {
    if (this.labelEl) this.labelEl.textContent = label || "Ошибка";
    if (this.barEl) this.barEl.classList.add("bg-red-500");
    this.setBusy(false);
  }

  show() {
    this.container?.classList.remove("hidden");
  }

  hide() {
    this.container?.classList.add("hidden");
  }
}

window.PipelineProgress = PipelineProgress;

window.ADE_PIPELINES = {
  workflow: [
    { key: "idea", label: "Идея" },
    { key: "tz", label: "ТЗ" },
    { key: "spec", label: "Spec" },
    { key: "code", label: "Код" },
    { key: "review", label: "Review" },
    { key: "deliverable", label: "Результат" },
  ],
  revise: [
    { key: "feedback", label: "Обратная связь" },
    { key: "architect", label: "Architect" },
    { key: "diff", label: "Сравнение" },
  ],
  rebuild: [
    { key: "queued", label: "Очередь" },
    { key: "coder", label: "Coder" },
    { key: "reviewer", label: "Reviewer" },
    { key: "mockup", label: "Превью" },
    { key: "deploy", label: "Деплой" },
    { key: "done", label: "Готово" },
  ],
};
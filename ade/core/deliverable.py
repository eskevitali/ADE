"""Detect deliverable type and build preview / install guidance."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

EXPO_SDK_MAJOR = 54
EXPO_PACKAGE_JSON: dict[str, Any] = {
    "name": "ade-mobile-app",
    "version": "1.0.0",
    "private": True,
    "main": "index.ts",
    "scripts": {
        "start": "expo start",
        "android": "expo start --android",
        "ios": "expo start --ios",
        "web": "expo start --web",
    },
    "dependencies": {
        "expo": "~54.0.35",
        "expo-status-bar": "~3.0.9",
        "react": "19.1.0",
        "react-native": "0.81.5",
    },
    "devDependencies": {
        "@types/react": "~19.1.0",
        "typescript": "~5.9.2",
    },
    "engines": {
        "node": ">=20.12.0",
    },
}


SIMULATOR_KW = (
    "симулятор",
    "simulator",
    "таймер",
    "timer",
    "демонстрац",
    "демо ",
    "интерактив",
)


def needs_interactive_simulator(idea: str, spec: str, *, feedback: str = "", code: str = "") -> bool:
    text = f"{idea}\n{spec}\n{feedback}\n{code}".lower()
    return any(k in text for k in SIMULATOR_KW)


def detect_project_type(idea: str, spec: str, code: str = "") -> str:
    text = f"{idea}\n{spec}\n{code}".lower()
    mobile_kw = (
        "ios",
        "android",
        "mobile",
        "react native",
        "expo",
        "flutter",
        "swift",
        "kotlin",
        "телефон",
        "мобильн",
    )
    web_kw = ("web", "browser", "fastapi", "react", "vue", "next.js", "веб", "сайт", "dashboard")
    if any(k in text for k in mobile_kw):
        return "mobile"
    if any(k in text for k in SIMULATOR_KW):
        return "simulator"
    if any(k in text for k in web_kw):
        return "web"
    return "other"


def _find_web_entry(src_dir: Path) -> str | None:
    for name in ("index.html", "app.html", "main.html"):
        if (src_dir / name).exists():
            return name
    return None


def build_deliverable(
    project_id: str,
    project_name: str,
    idea: str,
    spec: str,
    code: str,
    project_path: Path,
) -> dict[str, Any]:
    project_type = detect_project_type(idea, spec, code)
    src_dir = project_path / "src"
    base = {
        "project_id": project_id,
        "project_name": project_name,
        "type": project_type,
        "type_label": {
            "web": "Веб-приложение",
            "mobile": "Мобильное приложение",
            "simulator": "Интерактивный симулятор",
            "other": "Прочее",
        }[project_type],
    }

    sim_path = project_path / "preview" / "timer-simulator.html"
    if project_type == "simulator" or sim_path.exists():
        base["type"] = "simulator"
        base["type_label"] = "Интерактивный симулятор"
        base["preview_url"] = f"/preview/{project_id}/simulator"
        base["preview_label"] = "Открыть симулятор (браузер)"
        base["simulator_available"] = sim_path.exists()
        base["instructions"] = (
            "Интерактивный симулятор в браузере: меняйте скорость и смотрите, "
            "как переменные влияют на ход часов. После Deploy — та же ссылка или /run/…"
        )
    elif project_type == "web":
        entry = _find_web_entry(src_dir) if src_dir.is_dir() else None
        if entry:
            base["preview_url"] = f"/preview/{project_id}"
            base["preview_label"] = "Открыть веб-превью"
            base["instructions"] = "Статическая страница из src/ доступна по ссылке превью."
        else:
            base["preview_url"] = f"/projects/{project_id}"
            base["preview_label"] = "Страница проекта"
            base["instructions"] = (
                "Исходники в projects/{id}/src/. Для живого веб-приложения запустите "
                "docker-compose в каталоге проекта или разверните через Deployer (Step 07)."
            )
        base["deploy_hint"] = f"cd projects/{project_id} && docker compose up -d"

    elif project_type == "mobile":
        mockup_path = project_path / "preview" / "mobile-mockup.html"
        expo_dir = _expo_dir(project_path)
        base["preview_url"] = f"/preview/{project_id}/mobile"
        base["preview_label"] = "Симулятор макета (браузер)"
        base["mockup_available"] = mockup_path.exists()
        base["expo_available"] = (expo_dir / "package.json").exists()
        base["expo_path"] = f"projects/{project_id}/expo"
        if base["expo_available"]:
            base["expo_download_url"] = f"/api/projects/{project_id}/expo-download"
            base["expo_download_label"] = "Создать и скачать ZIP"
        base["instructions"] = _mobile_launch_instructions(project_name)
        base["simulator_exports"] = _mobile_local_commands()
    else:
        base["preview_url"] = f"/projects/{project_id}"
        base["preview_label"] = "Артефакты проекта"
        base["instructions"] = "См. spec/, src/ и review/ в каталоге проекта."

    return base


def write_deliverable_manifest(project_path: Path, deliverable: dict[str, Any]) -> None:
    path = project_path / "deliverable.json"
    path.write_text(json.dumps(deliverable, indent=2, ensure_ascii=False), encoding="utf-8")


def read_deliverable(project_path: Path) -> dict[str, Any] | None:
    path = project_path / "deliverable.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


EXPO_ZIP_NAME = "expo-mobile.zip"
EXPO_ZIP_SKIP_DIRS = frozenset({"node_modules", ".expo"})


def _expo_dir(project_path: Path) -> Path:
    return project_path / "expo"


def expo_zip_path(project_path: Path) -> Path:
    return project_path / EXPO_ZIP_NAME


def _mobile_launch_instructions(project_name: str) -> str:
    return (
        f"Запуск «{project_name}» на телефоне через Expo Go:\n"
        "1. Нажмите «Создать и скачать ZIP» (архив соберётся заново), распакуйте на компьютер.\n"
        "2. Установите Node.js 20+ (https://nodejs.org) и приложение Expo Go на телефон.\n"
        "   • iOS: App Store → «Expo Go»\n"
        "   • Android: Google Play → «Expo Go»\n"
        "3. В терминале откройте распакованную папку и выполните:\n"
        "   npm install\n"
        "   npx expo start\n"
        "4. Отсканируйте QR-код в Expo Go (телефон и компьютер — в одной Wi‑Fi сети).\n"
        "Подробности — в файле LAUNCH.md внутри архива."
    )


def _mobile_local_commands() -> list[dict[str, str]]:
    return [
        {"platform": "Expo Go (после распаковки ZIP)", "command": "npm install && npx expo start"},
        {
            "platform": "iOS Simulator (только Mac + Xcode)",
            "command": "npm install && npx expo run:ios",
        },
        {
            "platform": "Android Emulator (Android Studio на ПК)",
            "command": "npm install && npx expo run:android",
        },
    ]


def _write_expo_launch_readme(expo_dir: Path, project_name: str) -> None:
    expo_dir.joinpath("LAUNCH.md").write_text(
        f"""# {project_name} — запуск в Expo Go

## Что нужно

1. **Компьютер** с Node.js **20+** ([скачать](https://nodejs.org))
2. **Телефон** с приложением **Expo Go**:
   - [iOS — App Store](https://apps.apple.com/app/expo-go/id982107779)
   - [Android — Google Play](https://play.google.com/store/apps/details?id=host.exp.exponent)

## Шаги

```bash
# в папке с package.json (после распаковки ZIP)
npm install
npx expo start
```

В терминале появится QR-код. Откройте **Expo Go** на телефоне и отсканируйте его.

## Если QR не открывается

- Убедитесь, что телефон и компьютер в **одной Wi‑Fi сети**
- Попробуйте туннель: `npx expo start --tunnel`

## Симулятор (опционально)

- **Android:** установите Android Studio, затем `npx expo run:android`
- **iOS:** только на Mac с Xcode — `npx expo run:ios`

Сборка на сервере ADE не поддерживается — запускайте локально на своём ПК.
""",
        encoding="utf-8",
    )


def build_expo_zip(project_path: Path, project_name: str) -> Path | None:
    """Pack expo/ sources (without node_modules) into expo-mobile.zip."""
    expo_dir = _expo_dir(project_path)
    if not (expo_dir / "package.json").exists():
        return None
    _write_expo_launch_readme(expo_dir, project_name)
    zip_path = expo_zip_path(project_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(expo_dir.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(expo_dir)
            if any(part in EXPO_ZIP_SKIP_DIRS for part in rel.parts):
                continue
            archive.write(file_path, rel.as_posix())
    return zip_path


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "ade-mobile-app"


def _expo_sdk_major(package_json_path: Path) -> int | None:
    if not package_json_path.exists():
        return None
    try:
        data = json.loads(package_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    expo_ver = str(data.get("dependencies", {}).get("expo", ""))
    match = re.match(r"~?(\d+)", expo_ver)
    return int(match.group(1)) if match else None


def _expo_needs_refresh(expo_dir: Path) -> bool:
    package_json = expo_dir / "package.json"
    major = _expo_sdk_major(package_json)
    if major is None:
        return True
    return major < EXPO_SDK_MAJOR


def _write_expo_app_tsx(expo_dir: Path, project_name: str, button_label: str) -> None:
    expo_dir.joinpath("App.tsx").write_text(
        f"""import {{ StatusBar }} from "expo-status-bar";
import {{ Alert, Pressable, StyleSheet, Text, View }} from "react-native";

export default function App() {{
  return (
    <View style={{styles.container}}>
      <View style={{styles.phone}}>
        <Text style={{styles.title}}>{project_name}</Text>
        <Pressable
          style={{styles.button}}
          onPress={{() => Alert.alert("GPS", "Координаты отправлены")}}
        >
          <Text style={{styles.buttonText}}>{button_label}</Text>
        </Pressable>
      </View>
      <StatusBar style="light" />
    </View>
  );
}}

const styles = StyleSheet.create({{
  container: {{
    flex: 1,
    backgroundColor: "#0b0f19",
    alignItems: "center",
    justifyContent: "center",
  }},
  phone: {{
    width: 320,
    padding: 24,
    borderRadius: 28,
    backgroundColor: "#111827",
    alignItems: "center",
    gap: 20,
  }},
  title: {{
    color: "#e5e7eb",
    fontSize: 16,
    fontWeight: "600",
  }},
  button: {{
    width: "100%",
    paddingVertical: 18,
    borderRadius: 16,
    backgroundColor: "#4f46e5",
    alignItems: "center",
  }},
  buttonText: {{
    color: "#fff",
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: 1,
  }},
}});
""",
        encoding="utf-8",
    )


def ensure_expo_project(
    project_path: Path,
    project_name: str,
    spec: str,
    *,
    feedback: str = "",
) -> Path:
    """Scaffold or refresh a minimal Expo SDK 54 app (Expo Go compatible)."""
    expo_dir = _expo_dir(project_path)
    expo_dir.mkdir(parents=True, exist_ok=True)
    button_label = _extract_button_label(spec, feedback)
    slug = _slugify(project_name)

    package_data = {
        **EXPO_PACKAGE_JSON,
        "name": slug,
    }
    (expo_dir / "package.json").write_text(
        json.dumps(package_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (expo_dir / "app.json").write_text(
        json.dumps(
            {
                "expo": {
                    "name": project_name,
                    "slug": slug,
                    "version": "1.0.0",
                    "orientation": "portrait",
                    "userInterfaceStyle": "dark",
                    "ios": {"supportsTablet": False},
                    "android": {"adaptiveIcon": {"backgroundColor": "#111827"}},
                }
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (expo_dir / "index.ts").write_text(
        """import { registerRootComponent } from "expo";

import App from "./App";

registerRootComponent(App);
""",
        encoding="utf-8",
    )
    (expo_dir / "tsconfig.json").write_text(
        """{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true
  }
}
""",
        encoding="utf-8",
    )
    (expo_dir / ".gitignore").write_text(
        "node_modules/\n.expo/\ndist/\nweb-build/\n",
        encoding="utf-8",
    )
    (expo_dir / ".nvmrc").write_text("20\n", encoding="utf-8")
    _write_expo_app_tsx(expo_dir, project_name, button_label)
    return expo_dir


def refresh_expo_project_if_stale(
    project_path: Path,
    project_name: str,
    spec: str,
    *,
    feedback: str = "",
) -> Path | None:
    """Upgrade legacy Expo scaffolds to the current SDK."""
    expo_dir = _expo_dir(project_path)
    if not _expo_needs_refresh(expo_dir):
        return None
    return ensure_expo_project(project_path, project_name, spec, feedback=feedback)


def _extract_button_label(spec: str, feedback: str = "") -> str:
    for text in (feedback, spec):
        if re.search(r"я\s*тут", text, re.IGNORECASE):
            return "Я ТУТ"
        match = re.search(r'кнопк[аиею].{0,40}?["«]([^"»\n]+)["»]', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r'["«](Я\s*ТУТ|Отправить[^"»\n]*)["»]', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "Я ТУТ"


def ensure_mobile_mockup(
    project_path: Path,
    project_name: str,
    spec: str,
    *,
    feedback: str = "",
) -> Path:
    """Create a minimal phone-frame UI mockup (no spec text dump)."""
    preview_dir = project_path / "preview"
    preview_dir.mkdir(exist_ok=True)
    mockup = preview_dir / "mobile-mockup.html"
    button_label = _extract_button_label(spec, feedback)
    mockup.write_text(
        f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{project_name} — Mockup</title>
  <style>
    body {{ margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
      background: #0b0f19; font-family: system-ui, sans-serif; color: #e5e7eb; }}
    .phone {{ width: 320px; height: 640px; border: 12px solid #1f2937; border-radius: 36px;
      background: linear-gradient(180deg, #1e1b4b, #111827); box-shadow: 0 25px 50px rgba(0,0,0,.5);
      overflow: hidden; display: flex; flex-direction: column; position: relative; }}
    .status {{ padding: 12px 16px; font-size: 12px; text-align: center; background: rgba(0,0,0,.3);
      display: flex; align-items: center; justify-content: space-between; }}
    .gps-dot {{ width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 6px #10b981; }}
    .content {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 24px 20px; gap: 16px; }}
    .btn-main {{ width: 100%; max-width: 240px; padding: 20px; border: none; border-radius: 16px;
      background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; font-size: 22px;
      font-weight: 700; letter-spacing: 0.05em; cursor: pointer; box-shadow: 0 8px 24px rgba(99,102,241,.4); }}
    .btn-main:active {{ transform: scale(0.97); }}
    .settings {{ position: absolute; top: 52px; right: 16px; }}
    .settings-btn {{ background: rgba(255,255,255,.1); border: none; color: #9ca3af; width: 36px; height: 36px;
      border-radius: 10px; cursor: pointer; font-size: 18px; }}
    .settings-panel {{ display: none; position: absolute; top: 96px; right: 16px; width: 200px;
      background: #1f2937; border-radius: 12px; padding: 12px; font-size: 13px; box-shadow: 0 8px 24px rgba(0,0,0,.4); }}
    .settings-panel.open {{ display: block; }}
    .settings-panel label {{ display: block; color: #9ca3af; margin-bottom: 4px; font-size: 11px; }}
    .settings-panel select {{ width: 100%; background: #111827; color: #e5e7eb; border: 1px solid #374151;
      border-radius: 8px; padding: 6px 8px; margin-bottom: 8px; }}
  </style>
</head>
<body>
  <div class="phone">
    <div class="status">
      <span class="gps-dot" title="GPS активен"></span>
      <span>{project_name}</span>
      <span style="width:8px"></span>
    </div>
    <div class="settings">
      <button class="settings-btn" onclick="document.getElementById('panel').classList.toggle('open')" title="Настройки">⚙</button>
      <div id="panel" class="settings-panel">
        <label>Контакт</label>
        <select><option>Выбрать контакт…</option></select>
        <label>Способ отправки</label>
        <select><option>SMS</option><option>WhatsApp</option><option>Telegram</option></select>
      </div>
    </div>
    <div class="content">
      <button class="btn-main" onclick="alert('GPS: координаты отправлены')">{button_label}</button>
    </div>
  </div>
</body>
</html>""",
        encoding="utf-8",
    )
    return mockup


def _src_needs_timer_scaffold(main_py: Path) -> bool:
    if not main_py.exists():
        return True
    content = main_py.read_text(encoding="utf-8", errors="ignore")
    if "class TimerSimulator" in content:
        try:
            compile(content, str(main_py), "exec")
            return False
        except SyntaxError:
            return True
    try:
        compile(content, str(main_py), "exec")
    except SyntaxError:
        return True
    return True


def _timer_simulator_html(project_name: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{project_name} — Симулятор таймера</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
      background: radial-gradient(ellipse at top, #1e1b4b, #0b0f19); font-family: system-ui, sans-serif; color: #e5e7eb; }}
    .panel {{ width: min(480px, 96vw); padding: 28px; border-radius: 20px;
      background: rgba(17,24,39,.92); border: 1px solid rgba(99,102,241,.35); box-shadow: 0 20px 60px rgba(0,0,0,.45); }}
    h1 {{ margin: 0 0 6px; font-size: 1.1rem; color: #a5b4fc; font-weight: 600; }}
    .clock {{ font-size: 3.5rem; font-weight: 700; letter-spacing: 0.06em; text-align: center;
      margin: 20px 0; font-variant-numeric: tabular-nums; color: #f9fafb;
      text-shadow: 0 0 30px rgba(99,102,241,.5); }}
    .vars {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 16px 0; font-size: 13px; }}
    .var {{ background: #111827; border-radius: 10px; padding: 10px 12px; }}
    .var span {{ display: block; color: #9ca3af; font-size: 11px; margin-bottom: 4px; }}
    .var strong {{ color: #c4b5fd; font-family: ui-monospace, monospace; }}
    label {{ display: block; font-size: 12px; color: #9ca3af; margin-bottom: 6px; }}
    input[type=range] {{ width: 100%; accent-color: #6366f1; }}
    .speed-presets {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 18px; }}
    .speed-presets button {{ flex: 1; min-width: 70px; padding: 8px 10px; border: 1px solid #374151;
      border-radius: 10px; background: #1f2937; color: #e5e7eb; cursor: pointer; font-size: 13px; }}
    .speed-presets button.active {{ border-color: #6366f1; background: #312e81; color: #e0e7ff; }}
    .controls {{ display: flex; gap: 10px; }}
    .controls button {{ flex: 1; padding: 12px; border: none; border-radius: 12px; font-weight: 600; cursor: pointer; }}
    .btn-start {{ background: linear-gradient(135deg, #10b981, #059669); color: white; }}
    .btn-pause {{ background: #374151; color: #e5e7eb; }}
    .btn-reset {{ background: #4c1d95; color: #ede9fe; }}
    .hint {{ margin-top: 16px; font-size: 12px; color: #6b7280; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="panel">
    <h1>{project_name}</h1>
    <p style="margin:0;color:#9ca3af;font-size:13px">Симулятор таймера — переменные меняют ход часов</p>
    <div class="clock" id="clock">12:00:00</div>
    <div class="vars">
      <div class="var"><span>speed_multiplier</span><strong id="v-speed">1.0</strong></div>
      <div class="var"><span>current_time (сек)</span><strong id="v-time">43200</strong></div>
      <div class="var"><span>tick_count</span><strong id="v-ticks">0</strong></div>
      <div class="var"><span>is_running</span><strong id="v-running">false</strong></div>
    </div>
    <label>Скорость симуляции (speed_multiplier)</label>
    <input type="range" id="speed-slider" min="-10" max="50" step="0.1" value="1">
    <div class="speed-presets">
      <button type="button" data-speed="0.1">0.1×</button>
      <button type="button" data-speed="1" class="active">1×</button>
      <button type="button" data-speed="10">10×</button>
      <button type="button" data-speed="-1">−1×</button>
    </div>
    <div class="controls">
      <button type="button" class="btn-start" id="btn-start">Старт</button>
      <button type="button" class="btn-pause" id="btn-pause">Пауза</button>
      <button type="button" class="btn-reset" id="btn-reset">Сброс 12:00</button>
    </div>
    <p class="hint">Измените <code>speed_multiplier</code> во время работы — часы ускорятся, замедлятся или пойдут назад. Это и есть демонстрация влияния переменных на симуляцию.</p>
  </div>
  <script>
    const state = {{
      current_time: 12 * 3600,
      speed_multiplier: 1.0,
      is_running: false,
      paused: false,
      tick_count: 0,
      last_ts: null,
    }};
    const el = (id) => document.getElementById(id);
    function formatTime(sec) {{
      sec = ((sec % 86400) + 86400) % 86400;
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const s = Math.floor(sec % 60);
      return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
    }}
    function render() {{
      el("clock").textContent = formatTime(state.current_time);
      el("v-speed").textContent = state.speed_multiplier.toFixed(1);
      el("v-time").textContent = Math.floor(state.current_time);
      el("v-ticks").textContent = state.tick_count;
      el("v-running").textContent = state.is_running && !state.paused ? "true" : "false";
    }}
    function setSpeed(v) {{
      state.speed_multiplier = v;
      el("speed-slider").value = v;
      document.querySelectorAll(".speed-presets button").forEach((b) => {{
        b.classList.toggle("active", parseFloat(b.dataset.speed) === v);
      }});
      render();
    }}
    function tick(ts) {{
      if (!state.is_running || state.paused) {{ state.last_ts = ts; return; }}
      if (state.last_ts != null) {{
        const dt = (ts - state.last_ts) / 1000;
        state.current_time += dt * state.speed_multiplier;
        state.tick_count += 1;
      }}
      state.last_ts = ts;
      render();
      requestAnimationFrame(tick);
    }}
    el("speed-slider").addEventListener("input", (e) => setSpeed(parseFloat(e.target.value)));
    document.querySelectorAll(".speed-presets button").forEach((b) => {{
      b.addEventListener("click", () => setSpeed(parseFloat(b.dataset.speed)));
    }});
    el("btn-start").addEventListener("click", () => {{
      state.is_running = true; state.paused = false; state.last_ts = null;
      render(); requestAnimationFrame(tick);
    }});
    el("btn-pause").addEventListener("click", () => {{ state.paused = !state.paused; render(); }});
    el("btn-reset").addEventListener("click", () => {{
      state.current_time = 12 * 3600; state.tick_count = 0; state.last_ts = null; render();
    }});
    render();
  </script>
</body>
</html>"""


def _timer_main_py_scaffold() -> str:
    return '''"""Hello function and TimerSimulator — console reference implementation."""

from __future__ import annotations

import time


def hello() -> None:
    print("Hello, World!")


class TimerSimulator:
    """Simulates clock time with adjustable speed_multiplier variable."""

    def __init__(self, start_time: int = 12 * 3600, speed: float = 1.0) -> None:
        self.current_time = float(start_time)
        self.speed_multiplier = float(speed)
        self.is_running = False
        self.paused = False
        self.tick_count = 0

    def format_time(self) -> str:
        sec = int(self.current_time) % 86400
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def set_speed(self, multiplier: float) -> None:
        self.speed_multiplier = multiplier

    def start(self) -> None:
        self.is_running = True
        self.paused = False

    def pause(self) -> None:
        self.paused = not self.paused

    def stop(self) -> None:
        self.is_running = False
        self.paused = False

    def tick(self, dt: float = 1.0) -> None:
        if self.is_running and not self.paused:
            self.current_time += dt * self.speed_multiplier
            self.tick_count += 1

    def status(self) -> dict:
        return {
            "time": self.format_time(),
            "current_time": self.current_time,
            "speed_multiplier": self.speed_multiplier,
            "tick_count": self.tick_count,
            "is_running": self.is_running,
            "paused": self.paused,
        }


def main() -> None:
    hello()
    sim = TimerSimulator()
    print("TimerSimulator ready. Open /preview/.../simulator in ADE for full web UI.")
    sim.start()
    for step, speed in enumerate([1.0, 10.0, 0.1, -1.0], start=1):
        sim.set_speed(speed)
        print(f"Step {step}: speed_multiplier={speed}")
        for _ in range(3):
            sim.tick(1.0)
            print(f"  {sim.format_time()} ticks={sim.tick_count}")
            time.sleep(0.3)
    sim.stop()
    print("Done:", sim.status())


if __name__ == "__main__":
    main()
'''


def ensure_timer_simulator(
    project_path: Path,
    project_name: str,
    spec: str,
    *,
    feedback: str = "",
) -> Path:
    """Interactive browser simulator + valid Python TimerSimulator scaffold."""
    preview_dir = project_path / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    sim_html = preview_dir / "timer-simulator.html"
    sim_html.write_text(_timer_simulator_html(project_name), encoding="utf-8")

    main_py = project_path / "src" / "main.py"
    main_py.parent.mkdir(parents=True, exist_ok=True)
    if _src_needs_timer_scaffold(main_py):
        main_py.write_text(_timer_main_py_scaffold(), encoding="utf-8")

    return sim_html
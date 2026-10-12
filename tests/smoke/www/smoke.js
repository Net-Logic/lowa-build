'use strict';
// Smoke test of a LOWA engine: opens and stores one file per format, then reports locale information.
(function () {
	const t0 = performance.now();
	const params = new URLSearchParams(location.search);
	const exts = (params.get('files') || 'odt,ods,odp,odg,docx,xlsx,pptx').split(',');
	const abs = (u) => new URL(u, location.href).href;
	const SMOKE = window.SMOKE = {done: false, error: null, results: [], probe: null};
	window.Module = {
		canvas: document.getElementById('qtcanvas'),
		uno_scripts: [abs('zeta.js'), abs('smoke_thread.js')],
		locateFile: (p) => abs('engine/' + p),
		mainScriptUrlOrBlob: new Blob(["importScripts('" + abs('engine/soffice.js') + "');"], {type: 'text/javascript'}),
		preRun: [],
		onAbort: (what) => { SMOKE.error = 'abort: ' + what; SMOKE.done = true; },
	};
	if (params.get('lang')) {
		Module.preRun.push(() => { ENV.LANG = params.get('lang') + '.UTF-8'; });
	}
	// dicts=1: Hunspell files in the system dictionary directory of the build, before LibreOffice starts
	const dicts = params.get('dicts') === '1' ? ['en_US.dic', 'en_US.aff', 'fr.dic', 'fr.aff'] : [];
	const dictData = {};
	if (dicts.length) {
		Module.preRun.push(() => {
			FS.mkdirTree('/usr/share/hunspell');
			for (const name of dicts) {
				FS.writeFile('/usr/share/hunspell/' + name.replace(/^fr\./, 'fr_FR.'), dictData[name]);
			}
		});
	}
	if (params.get('ui')) {
		Module.preRun.push(() => { ENV.LC_MESSAGES = params.get('ui') + '.UTF-8'; });
	}
	const finish = async () => {
		SMOKE.t_done_ms = Math.round(performance.now() - t0);
		try {
			SMOKE.memory_bytes = (await performance.measureUserAgentSpecificMemory()).bytes;
		} catch (e) {
			SMOKE.memory_bytes = null;
		}
		SMOKE.done = true;
	};
	const script = document.createElement('script');
	script.src = abs('engine/soffice.js');
	script.onerror = () => { SMOKE.error = 'soffice.js failed to load'; SMOKE.done = true; };
	script.onload = () => {
		Module.uno_main.then((port) => {
			port.onmessage = async (e) => {
				const d = e.data;
				if (d.cmd === 'ready') {
					SMOKE.t_ready_ms = Math.round(performance.now() - t0);
					try { FS.mkdir('/tmp/smoke'); } catch (err) { /* exists */ }
					const paths = [];
					for (const ext of exts) {
						const res = await fetch(abs('samples/sample.' + ext));
						FS.writeFile('/tmp/smoke/sample.' + ext, new Uint8Array(await res.arrayBuffer()));
						paths.push('/tmp/smoke/sample.' + ext);
					}
					port.postMessage({cmd: 'run', files: paths, visible: params.get('visible') === '1'});
				} else if (d.cmd === 'result') {
					if (d.ok) {
						const bytes = FS.readFile(d.file);
						d.bytes = bytes.length;
						if (bytes[0] !== 0x50 || bytes[1] !== 0x4b) {
							d.ok = false;
							d.message = 'stored file is not a zip';
						}
					}
					SMOKE.results.push(d);
				} else if (d.cmd === 'probe') {
					SMOKE.probe = d.value;
				} else if (d.cmd === 'done') {
					finish();
				}
			};
		});
	};
	Promise.all(dicts.map((name) => fetch(abs('dicts/' + name)).then((r) => r.arrayBuffer()).then((b) => { dictData[name] = new Uint8Array(b); })))
		.then(() => document.body.appendChild(script));
})();

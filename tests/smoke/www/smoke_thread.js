'use strict';
// Worker side of the smoke test: open, store, close each file; read the locale settings.
let zetajs;
let css;

function message(err) {
	try {
		const exc = zetajs.catchUnoException(err);
		return String(exc.Message || exc);
	} catch (e) {
		return String(err);
	}
}

function config(ctx, path, name) {
	try {
		// Read the singleton by name: zetajs 1.2.0's singleton accessors return undefined
		const provider = zetajs.fromAny(ctx.getValueByName('/singletons/com.sun.star.configuration.theDefaultProvider'));
		const access = provider.createInstanceWithArguments('com.sun.star.configuration.ConfigurationAccess',
			[new css.beans.PropertyValue({Name: 'nodepath', Value: path})]);
		return String(zetajs.fromAny(access.getByName(name)));
	} catch (e) {
		return 'ERROR ' + message(e);
	}
}

// writerDoc: a new document, whose text language is the default for new text
function probe(ctx, writerDoc) {
	const value = {
		ooLocale: config(ctx, '/org.openoffice.Setup/L10N', 'ooLocale'),
		ooSetupSystemLocale: config(ctx, '/org.openoffice.Setup/L10N', 'ooSetupSystemLocale'),
		uiLocale: config(ctx, '/org.openoffice.Office.Linguistic/General', 'UILocale'),
		defaultLocale: config(ctx, '/org.openoffice.Office.Linguistic/General', 'DefaultLocale'),
	};
	try {
		value.userDir = String(css.util.PathSubstitution.create(ctx).substituteVariables('$(user)', true));
	} catch (e) {
		value.userDir = 'ERROR ' + message(e);
	}
	try {
		const commands = zetajs.fromAny(zetajs.fromAny(ctx.getValueByName('/singletons/com.sun.star.frame.theUICommandDescription'))
			.getByName('com.sun.star.text.TextDocument'));
		const props = zetajs.fromAny(commands.getByName('.uno:Save'));
		value.saveLabel = String(zetajs.fromAny(props.find((p) => p.Name === 'Label').Value));
	} catch (e) {
		value.saveLabel = 'ERROR ' + message(e);
	}
	try {
		const loc = zetajs.fromAny(writerDoc.getText().createTextCursor().getPropertyValue('CharLocale'));
		value.charLocale = loc.Language + '-' + loc.Country;
	} catch (e) {
		value.charLocale = 'ERROR ' + message(e);
	}
	try {
		// Through the dispatcher, as Writer does. zetajs resolves its isValid to XSpellChecker1::isValid, which takes
		// a LanguageType (Windows LCID) instead of a Locale
		const LCID = {'en-US': 1033, 'en-GB': 2057, 'fr-FR': 1036, 'fr-BE': 2060, 'fr-CH': 4108, 'de-DE': 1031,
			'de-CH': 2055, 'es-ES': 3082, 'es-MX': 2058, 'it-IT': 1040, 'it-CH': 2064};
		const WORDS = {en: ['hello', 'helo'], fr: ['bonjour', 'bonjuor'], de: ['Haus', 'Huas'], es: ['casa', 'csaa'], it: ['ciao', 'ciaoo']};
		const dispatcher = css.linguistic2.LinguServiceManager.create(ctx).getSpellChecker();
		const checks = {};
		for (const [loc, lcid] of Object.entries(LCID)) {
			const [good, bad] = WORDS[loc.split('-')[0]];
			checks[loc] = {valid: dispatcher.isValid(good, lcid, []), rejected: !dispatcher.isValid(bad, lcid, [])};
		}
		value.spelling = {
			locales: zetajs.fromAny(dispatcher.getLocales()).map((l) => l.Language + '-' + l.Country).join(' '),
			checks: checks,
		};
	} catch (e) {
		value.spelling = 'ERROR ' + message(e);
	}
	try {
		const hyph = css.linguistic2.LinguServiceManager.create(ctx).getHyphenator();
		const WORDS = {'en-US': 'hyphenation', 'fr-FR': 'anticonstitutionnellement', 'de-DE': 'Donaudampfschifffahrt',
			'es-ES': 'electroencefalografista', 'es-MX': 'electroencefalografista', 'it-IT': 'precipitevolissimevolmente'};
		const words = {};
		for (const [loc, word] of Object.entries(WORDS)) {
			const [lang, country] = loc.split('-');
			const res = hyph.hyphenate(word, new css.lang.Locale({Language: lang, Country: country, Variant: ''}), word.length - 2, []);
			words[loc] = res ? res.getHyphenPos() : null;
		}
		value.hyphenation = {
			locales: zetajs.fromAny(hyph.getLocales()).map((l) => l.Language + '-' + l.Country).join(' '),
			words: words,
		};
	} catch (e) {
		value.hyphenation = 'ERROR ' + message(e);
	}
	return value;
}

Module.zetajs.then(function (z) {
	zetajs = z;
	css = z.uno.com.sun.star;
	const ctx = zetajs.getUnoComponentContext();
	const desktop = css.frame.Desktop.create(ctx);
	zetajs.mainPort.onmessage = function (e) {
		const d = e.data;
		if (d.cmd !== 'run') {
			return;
		}
		d.files.forEach((path, i) => {
			const last = i === d.files.length - 1;
			try {
				const props = [new css.beans.PropertyValue({Name: 'Hidden', Value: !(d.visible && last)})];
				const doc = desktop.loadComponentFromURL('file://' + path, '_default', 0, props);
				if (!doc) {
					throw new Error('not loaded');
				}
				doc.store();
				if (!(d.visible && last)) {
					doc.close(true);
				}
				zetajs.mainPort.postMessage({cmd: 'result', file: path, ok: true});
			} catch (err) {
				zetajs.mainPort.postMessage({cmd: 'result', file: path, ok: false, message: message(err)});
			}
		});
		const writerDoc = desktop.loadComponentFromURL('private:factory/swriter', '_default', 0,
			[new css.beans.PropertyValue({Name: 'Hidden', Value: true})]);
		zetajs.mainPort.postMessage({cmd: 'probe', value: probe(ctx, writerDoc)});
		zetajs.mainPort.postMessage({cmd: 'done'});
	};
	zetajs.mainPort.postMessage({cmd: 'ready'});
});

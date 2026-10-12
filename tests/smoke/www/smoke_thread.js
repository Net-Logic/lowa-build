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

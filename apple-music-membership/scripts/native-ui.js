function run(argv) {
    const se = Application('System Events');
    const action = argv[0] || 'snapshot';
    const appName = argv[1] || 'Music';
    const proc = se.applicationProcesses.byName(appName);

    function get(obj, key, fallback) {
        try { const v = obj[key](); return v === null || v === undefined ? fallback : v; } catch (_) { return fallback; }
    }
    function attr(obj, key) { return get(obj, key, ''); }

    if (action === 'doctor') return JSON.stringify({accessibility: se.uiElementsEnabled()});

    if (!proc.exists()) {
        if (action === 'activate') {
            Application(appName).activate();
            return JSON.stringify({opened: appName, wasRunning: false});
        }
        throw Error(appName + ' not running');
    }

    if (action === 'activate') {
        proc.frontmost = true;
        return JSON.stringify({opened: appName, wasRunning: true});
    }

    function describe(el, index, win) {
        return {
            index: index,
            window: win,
            role: attr(el, 'role'),
            subrole: attr(el, 'subrole'),
            name: attr(el, 'name'),
            description: attr(el, 'description'),
            text: attr(el, 'value') === '' ? '' : String(get(el, 'value', '')).slice(0, 200),
            placeholder: attr(el, 'placeholderValue'),
            enabled: get(el, 'enabled', null)
        };
    }
    function collect(root, win, rows, depth) {
        if ((depth || 0) > 8 || !root) return rows;
        let kids = [];
        try { kids = root.uiElements(); } catch (_) { return rows; }
        for (let i = 0; i < kids.length; i++) {
            rows.push({element: kids[i], info: describe(kids[i], rows.length, win)});
            collect(kids[i], win, rows, (depth || 0) + 1);
        }
        return rows;
    }
    function windowRows() {
        const rows = [];
        const wins = get(proc, 'windows', []);
        for (let w = 0; w < wins.length; w++) {
            try {
                const contents = wins[w].uiElements();
                for (let i = 0; i < contents.length; i++) rows.push({element: contents[i], info: describe(contents[i], rows.length, String(get(wins[w], 'name', '')))});
                collect(wins[w], String(get(wins[w], 'name', '')), rows, 1);
            } catch (_) {}
        }
        return rows;
    }
    function sheetRoots() {
        const roots = [];
        const wins = get(proc, 'windows', []);
        for (let w = 0; w < wins.length; w++) {
            let sheets = [], dialogs = [];
            try { sheets = wins[w].sheets(); } catch (_) {}
            try { dialogs = wins[w].dialogs(); } catch (_) {}
            try { if (wins[w].subrole() === 'AXDialog') dialogs.push(wins[w]); } catch (_) {}
            roots.push.apply(roots, sheets);
            roots.push.apply(roots, dialogs);
        }
        return roots;
    }

    function matchNodes(rows, label, role) {
        const pool = rows.filter(function (x) { return (!role || x.info.role === role) && x.info.enabled !== false; });
        const pick = function (fn) { return pool.filter(function (x) { return fn(x.info); }); };
        const exact = pick(function (i) { return i.name === label || i.description === label || i.text === label; });
        if (exact.length) return {matches: exact, mode: 'exact'};
        const prefix = pick(function (i) { return [i.name, i.description, i.text].some(function (v) { return v && v.indexOf(label) === 0; }); });
        if (prefix.length) return {matches: prefix, mode: 'prefix'};
        const contains = pick(function (i) { return [i.name, i.description, i.text].some(function (v) { return v && v.indexOf(label) >= 0; }); });
        if (contains.length) return {matches: contains, mode: 'contains'};
        return {matches: [], mode: 'none'};
    }

    if (action === 'snapshot') {
        const rows = windowRows();
        let accountMenu = [];
        try {
            const bar = proc.menuBars[0];
            let account = bar.menuBarItems.byName('账户');
            if (!account.exists()) account = bar.menuBarItems.byName('Account');
            accountMenu = account.menus[0].menuItems().map(function (x) { return get(x, 'name', ''); });
        } catch (_) {}
        return JSON.stringify({app: appName, running: true,
            windows: get(proc, 'windows', []).map(function (x) { return get(x, 'name', ''); }),
            accountMenu: accountMenu, truncated: rows.length > 1600,
            nodes: rows.slice(0, 1600).map(function (x) { return x.info; })});
    }

    if (action === 'page-health') {
        const rows = windowRows().map(function (x) { return x.info; });
        const texts = rows.map(function (i) { return (i.name || '') + ' ' + (i.text || '') + ' ' + (i.description || ''); }).filter(function (t) { return t.trim(); });
        const errorText = texts.filter(function (t) { return /出错了|请稍后再试|Something went wrong|Try again later|无法载入|Cannot connect/i.test(t); })[0] || '';
        const labelCount = texts.filter(function (t) { return !/^(文本|按钮|组|滚动区|外框|外框行|单元格|图像|窗口|分离组)$/.test(t.trim()); }).length;
        const status = errorText ? 'error' : (labelCount <= 4 ? 'blank' : 'ok');
        return JSON.stringify({status: status, errorText: errorText.slice(0, 120), labelCount: labelCount, nodeCount: rows.length});
    }

    if (action === 'sheet' || action === 'wait') {
        const target = argv[2] || 'sheet';
        const timeoutMs = parseInt(argv[3] || '6000', 10);
        const startedAt = Date.now();
        const deadline = startedAt + timeoutMs;
        let roots = sheetRoots();
        if (action === 'wait') {
            while (Date.now() < deadline) {
                roots = sheetRoots();
                if (target === 'sheet' && roots.length) break;
                if (target && target !== 'sheet' && roots.length) {
                    const rows = [];
                    for (let r = 0; r < roots.length; r++) collect(roots[r], 'sheet', rows, 0);
                    const hit = rows.some(function (x) {
                        const i = x.info;
                        return [i.name, i.text, i.description].some(function (v) { return v && v.indexOf(target) >= 0; });
                    });
                    if (hit) break;
                }
                delay(0.3);
            }
        }
        if (!roots.length) return JSON.stringify({exists: false, waitedMs: action === 'wait' ? Date.now() - startedAt : 0, items: [], buttons: []});
        const rows = [];
        for (let r = 0; r < roots.length; r++) collect(roots[r], 'sheet', rows, 0);
        const buttons = rows.filter(function (x) { return x.info.role === 'AXButton' && (x.info.name || x.info.description); })
            .map(function (x) { return x.info.name || x.info.description; });
        const fields = rows.filter(function (x) { return x.info.role === 'AXTextField'; }).map(function (x) { return {label: x.info.name || x.info.description, length: String(x.info.text || '').length}; });
        const texts = [];
        rows.forEach(function (x) {
            const t = (x.info.name || x.info.text || '').trim();
            if (t && texts.indexOf(t) < 0 && (x.info.role === 'AXStaticText' || x.info.role === 'AXHeading')) texts.push(t);
        });
        return JSON.stringify({exists: true, itemCount: rows.length, buttons: buttons, fields: fields, texts: texts.slice(0, 40)});
    }

    if (action === 'account-settings' || action === 'redeem-menu') {
        const pattern = action === 'account-settings' ? /^(账户设置|Account Settings)/ : /^(兑换…?|兑换\.\.\.|Redeem…?|Redeem\.\.\.)/;
        let account = proc.menuBars[0].menuBarItems.byName('账户');
        if (!account.exists()) account = proc.menuBars[0].menuBarItems.byName('Account');
        const items = account.menus[0].menuItems();
        const matches = items.filter(function (x) { return pattern.test(get(x, 'name', '')); });
        if (matches.length !== 1) throw Error('Menu item not unique (found ' + matches.length + ') for ' + action);
        proc.frontmost = true;
        delay(0.2);
        const wasEnabled = get(matches[0], 'enabled', false);
        matches[0].click();
        return JSON.stringify({clicked: get(matches[0], 'name', ''), wasEnabled: wasEnabled, menus: items.map(function (x) { return get(x, 'name', ''); }).filter(function (n) { return n; })});
    }

    if (action === 'type') {
        const text = argv[2];
        if (!text) throw Error('Text required');
        const roots = sheetRoots();
        const scope = roots.length ? roots : [{uiElements: function () { return []; }}];
        const rows = [];
        for (let r = 0; r < scope.length; r++) collect(scope[r], 'sheet', rows, 0);
        let fields = rows.filter(function (x) { return x.info.role === 'AXTextField'; });
        if (!fields.length) fields = windowRows().filter(function (x) { return x.info.role === 'AXTextField'; });
        if (fields.length !== 1) throw Error('Expected exactly one text field, found ' + fields.length);
        proc.frontmost = true;
        fields[0].element.click();
        delay(0.5);
        se.keystroke(text);
        delay(0.8);
        let value = '';
        try { value = String(fields[0].element.value() || ''); } catch (_) {}
        return JSON.stringify({typed: text.length, fieldLength: value.length, matchesInput: value === text});
    }

    if (action === 'click') {
        const label = argv[2];
        const role = argv[3];
        const scope = argv[4] || 'auto';
        if (!label) throw Error('Observed label required');
        let rows = [];
        if (scope === 'sheet' || scope === 'auto') {
            const roots = sheetRoots();
            for (let r = 0; r < roots.length; r++) collect(roots[r], 'sheet', rows, 0);
        }
        if (!rows.length && scope !== 'sheet') rows = windowRows();
        const result = matchNodes(rows, label, role);
        if (result.matches.length !== 1) {
            const names = result.matches.slice(0, 6).map(function (x) { return x.info.role + ':' + (x.info.name || x.info.text || x.info.description); });
            throw Error('Target must match exactly once; found ' + result.matches.length + ' for "' + label + '"' + (names.length ? ' [' + names.join(' | ') + ']' : ''));
        }
        proc.frontmost = true;
        result.matches[0].element.click();
        return JSON.stringify({clicked: label, matchMode: result.mode, role: result.matches[0].info.role});
    }

    throw Error('Unknown action');
}

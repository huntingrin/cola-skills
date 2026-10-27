/* macOS JXA accessibility bridge. No credentials are read or entered. */
function run(argv) {
    const se = Application('System Events');
    const action = argv[0] || 'snapshot';
    const appName = argv[1] || 'Music';
    if (['Music', 'App Store'].indexOf(appName) === -1) throw Error('Unsupported app');
    function get(obj, key, fallback) {
        try { const v = obj[key](); return v === undefined || v === null ? fallback : v; }
        catch (_) { return fallback; }
    }
    function attr(obj, key) {
        try { return obj.attributes.byName(key).value(); } catch (_) { return ''; }
    }
    if (action === 'doctor') return JSON.stringify({accessibility: se.uiElementsEnabled()});
    if (action === 'activate') {
        Application(appName).activate();
        return JSON.stringify({opened: appName});
    }
    const proc = se.applicationProcesses.byName(appName);
    if (!proc.exists()) return JSON.stringify({app: appName, running: false, windows: []});
    const windows = proc.windows();
    function describe(el, index, win) {
        const role = get(el, 'role', '');
        const subrole = get(el, 'subrole', '');
        const secure = subrole === 'AXSecureTextField';
        // Some secure fields have no subrole: never inspect any text field value.
        return {window: win, index: index, role: role, subrole: subrole,
            name: secure ? '[密码框]' : get(el, 'name', ''),
            description: secure ? '[密码框]' : get(el, 'description', ''),
            text: role === 'AXStaticText' ? get(el, 'value', '') : '',
            placeholder: role === 'AXTextField' ? attr(el, 'AXPlaceholderValue') : '',
            enabled: get(el, 'enabled', true)};
    }
    function allNodes() {
        let rows = [];
        for (let w = 0; w < windows.length; w++) {
            const sheets = windows[w].sheets();
            const root = sheets.length ? sheets[sheets.length - 1] : windows[w];
            const contents = root.entireContents();
            for (let i = 0; i < contents.length; i++) {
                rows.push({element: contents[i], info: describe(contents[i], i, w)});
            }
        }
        return rows;
    }
    if (action === 'snapshot') {
        const rows = allNodes();
        let accountMenu = [];
        if (appName === 'Music') {
            try {
                const bar = proc.menuBars[0];
                let account = bar.menuBarItems.byName('账户');
                if (!account.exists()) account = bar.menuBarItems.byName('Account');
                accountMenu = account.menus[0].menuItems().map(function (x) { return get(x, 'name', ''); });
            } catch (_) {}
        }
        return JSON.stringify({app: appName, running: true,
            windows: windows.map(function (x) { return get(x, 'name', ''); }),
            accountMenu: accountMenu, truncated: rows.length > 1600,
            nodes: rows.slice(0, 1600).map(function (x) { return x.info; })});
    }
    if (action === 'account-settings') {
        let account = proc.menuBars[0].menuBarItems.byName('账户');
        if (!account.exists()) account = proc.menuBars[0].menuBarItems.byName('Account');
        const items = account.menus[0].menuItems();
        const matches = items.filter(function (x) { return /^(账户设置|Account Settings)/.test(get(x, 'name', '')); });
        if (matches.length !== 1 || !get(matches[0], 'enabled', false)) throw Error('Account settings unavailable; inspect current sheet');
        proc.frontmost = true;
        matches[0].click();
        return JSON.stringify({clicked: get(matches[0], 'name', '')});
    }
    if (action === 'click') {
        const label = argv[2];
        const role = argv[3];
        if (!label || !role) throw Error('Observed label and role required');
        // Re-find the exact semantic target in fresh UI, never reuse a numeric index.
        const matches = allNodes().filter(function (x) {
            return x.info.role === role && x.info.enabled &&
                (x.info.name === label || x.info.description === label || x.info.text === label);
        });
        if (matches.length !== 1) throw Error('Target must match exactly once; found ' + matches.length);
        proc.frontmost = true;
        matches[0].element.click();
        return JSON.stringify({clicked: label, role: role});
    }
    throw Error('Unknown action');
}

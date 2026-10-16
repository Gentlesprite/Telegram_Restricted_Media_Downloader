/* TRMD Web UI — 前端脚本(含从 telegram-tt 移植的渐变背景实现)
 * Copyright © 2024-2026 Gentlesprite
 * SPDX-License-Identifier: GPL-3.0-only
 * 本文件整体以 GNU GPL-3.0 授权;完整许可见仓库根目录 LICENCE。
 */
const EMPTY_SUMMARY = {percent: 0, info: '0.00B / 0.00B', speed: '', remaining: ''};

var SECTIONS = {
    download: ['download'],
    upload: ['upload'],
    listener: ['listener'],
    storage: ['storage']  // 存储页:展示数据库中的下载与上传历史,不依赖机器人。
};
var PAGES = SECTIONS.download.concat(SECTIONS.upload, SECTIONS.listener, SECTIONS.storage);  // 下载、上传、记录各一个页面,监听页只在内部切换选项卡。
var SUMMARY_IDS = {
    download: {fill: 'overallFill', percent: 'overallPercent', info: 'overallInfo', extra: 'overallExtra'},
    upload: {fill: 'uploadFill', percent: 'uploadPercent', info: 'uploadInfo', extra: 'uploadExtra'}
};  // 下载与上传各自独立的总进度面板,避免相互覆盖。
var SECTION_KEY = 'trmd_section';
var LISTEN_KEY = 'trmd_listen';
var HAS_BOT = document.body.getAttribute('data-bot') === '1';  // 是否配置了机器人,决定上传/监听侧边栏是否展示(无机器人时只有下载可用)。
var HAS_STORAGE = document.body.getAttribute('data-storage') === '1';  // 记录数据库是否可用,决定记录侧边栏是否展示(记录功能不依赖机器人)。
var COLLAPSE_KEY = 'trmd_collapsed';  // 各分组折叠状态的本地存储键。
var ALL_KEY = 'trmd_all_collapsed';  // 下载页全部折叠开关的本地存储键。
var UPLOAD_ALL_KEY = 'trmd_upload_all_collapsed';  // 上传页全部折叠开关的本地存储键。
var LINK_LAST_KEY = 'trmd_link_last';  // 下载页链接层最后一次手动选择的本地存储键。
var UPLOAD_LAST_KEY = 'trmd_upload_last';  // 上传页频道层最后一次手动选择的本地存储键。
var LISTEN_TABS = ['forward', 'download'];  // 监听页的选项卡:转发、下载。

var STATE_TEXT = {
    pending: '队列中',  // 排队中,尚未开始处理(对应后端 DownloadStatus.PENDING)。
    downloading: '下载中',
    success: '已完成',
    skip: '已跳过',
    failure: '失败'
};
var STATE_CLASS = {
    pending: 'status-pending',
    downloading: 'status-running',
    success: 'status-done',
    skip: 'status-skip',
    failure: 'status-failed'
};
var STATE_ICON = {
    pending: '⏳',
    downloading: '📥',
    success: '✅',
    skip: '⏭',
    failure: '❌'
};

var HEAD_LABELS = ['频道', '频道 / 链接', '频道 / 链接 / 名称'];  // 表头首列随当前展开的层级变化。
var SIZE_LABELS = ['完成 / 总数', '完成 / 总数', '数量 / 大小'];  // 第三列同理,分组行是数量,成员行才是字节大小。
var UPLOAD_HEAD_NAME = ['频道', '频道 / 文件路径'];  // 上传页只有频道与文件两级。
var UPLOAD_HEAD_SIZE = ['完成 / 总数', '大小'];
var UPLOAD_TEXT = {
    pending: '队列中',
    uploading: '上传中',
    success: '已完成',
    sent: '已完成',
    failure: '失败'
};
var UPLOAD_CLASS = {
    pending: 'status-pending',
    uploading: 'status-running',
    success: 'status-done',
    sent: 'status-done',
    failure: 'status-failed'
};
var UPLOAD_ICON = {
    pending: '⏳',
    uploading: '📤',
    success: '✅',
    sent: '✅',
    failure: '❌'
};
var collapsed = {};
var allCollapsed = false;
var uploadAllCollapsed = false;
var lastLinkCollapsed = true;  // 下载页链接层最后的手动选择,缺省折叠以保持原有默认。
var lastUploadCollapsed = false;  // 上传页频道层最后的手动选择,缺省展开以保持原有默认。
var UNGROUPED_NAME = '未分组';
var currentSection = 'download';
var currentListen = 'forward';
var lastSnapshot = null;  // 缓存最近一次进度快照,供设置弹窗回填当前保存目录。
var lastDownloadActive = 0;
var lastUploadActive = 0;
var lastListenCount = 0;
var lastPaused = false;  // 全局暂停状态,随进度快照更新,供顶栏状态与按钮联动。
var lastUploadFinished = 0;  // 上传已结束(成功 + 失败)的任务数,用于驱动背景渐变步进。

function esc(text) {
    var div = document.createElement('div');
    div.textContent = text === undefined || text === null ? '' : text;
    return div.innerHTML;
}

function escAttr(text) {
    return esc(text).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function dash(text) {
    return text ? esc(text) : '—';
}

function progressCell(percent) {
    // --p 供手机端把横向条换成圆环时使用(带 % 的完整角度值);桌面端不读取,无副作用。
    return '<span class="cell-progress" style="--p:' + percent + '%">' +
        '<span class="track"><span class="fill" style="width:' + percent + '%"></span></span>' +
        '<span class="pct">' + percent + '%</span></span>';
}

var SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];  // 与终端的十进制单位保持一致。

function sizeText(bytes) {
    var value = Number(bytes) || 0;
    var index = 0;
    while (value >= 1000 && index < SIZE_UNITS.length - 1) {
        value = value / 1000;
        index++;
    }
    return value.toFixed(2) + SIZE_UNITS[index];
}

function secondsText(seconds) {
    var total = Math.floor(Number(seconds) || 0);
    if (total < 60) {
        return total + '秒';
    }
    if (total < 3600) {
        return Math.floor(total / 60) + '分' + (total % 60) + '秒';
    }
    return Math.floor(total / 3600) + '时' + Math.floor(total % 3600 / 60) + '分' + (total % 60) + '秒';
}

function groupStat(members, live) {
    var speed = 0;
    var left = 0;
    for (var i = 0; i < members.length; i++) {
        var member = members[i];
        var task = live[member.task_id] || member;  // 上传成员自带进度字段,查不到进度条任务时回退到自身。
        if (member.state === 'success' || member.state === 'skip' || member.state === 'sent') {
            continue;  // 已完成、已跳过、已发送的成员不再计入速度与剩余。
        }
        if (task && task.speed_value) {
            speed += Number(task.speed_value) || 0;
        }
        left += Math.max((Number(member.size_byte) || 0) - (Number(task && task.completed) || 0), 0);
    }
    return {speed: speed, remaining: speed && left > 0 ? left / speed : null};
}

function groupStatCells(stat) {
    var speed = stat.speed ? sizeText(stat.speed) + '/s' : '—';
    var remain = stat.remaining === null ? '—' : secondsText(stat.remaining);
    return '<span class="cell-speed">' + speed + '</span>' +
        '<span class="cell-remain">' + remain + '</span>';
}

function taskRow(task) {
    var done = task.percent >= 100;
    // data-task-id 供"列表结构未变时就地更新进度",避免每秒整表重建。
    return '<div class="task-row" data-task-id="' + escAttr(task.id) + '">' +
        '<span class="cell-name"><span class="ficon">' + esc(task.type || '📄') + '</span>' +
        '<span class="fname" title="' + escAttr(task.filename) + '">' + esc(task.filename) + '</span></span>' +
        progressCell(task.percent) +
        '<span class="cell-size">' + dash(task.info) + '</span>' +
        '<span class="cell-speed">' + dash(task.speed) + '</span>' +
        '<span class="cell-remain">' + dash(task.remaining) + '</span>' +
        '<span class="cell-status ' + (done ? 'status-done' : 'status-running') + '">' +
        (done ? '已完成' : '下载中') + '</span>' +
        '</div>';
}

function memberRow(item) {
    var state = item.state || 'pending';
    var text = STATE_TEXT[state] || '队列中';
    var cls = STATE_CLASS[state] || 'status-pending';
    var pending = state === 'pending';
    var progress;
    if (state === 'success') {
        progress = progressCell(100);
    } else if (item.note) {  // 不支持或被忽略的类型拿不到文件类型,进度栏改为显示具体原因,避免与普通跳过混淆。
        progress = '<span class="cell-progress"><span class="pct note" title="' + escAttr(item.note) + '">' +
            esc(item.note) + '</span></span>';
    } else {
        progress = '<span class="cell-progress"><span class="pct' + (pending ? ' pending' : '') + '">' + text + '</span></span>';
    }
    return '<div class="task-row member-row">' +
        '<span class="cell-name"><span class="ficon">' + (STATE_ICON[state] || '⏳') + '</span>' +
        '<span class="fname" title="' + escAttr(item.name) + '">' + esc(item.name) + '</span>' +
        (item.date ? '<span class="gcount">' + esc(item.date) + '</span>' : '') +
        '</span>' +
        progress +
        '<span class="cell-size">' + dash(item.size) + '</span>' +
        '<span class="cell-speed">—</span>' +
        '<span class="cell-remain">—</span>' +
        '<span class="cell-status ' + cls + '">' + text + '</span>' +
        '</div>';
}

function linkStatusCell(link) {
    var remaining = link.remaining || 0;
    var failed = link.failed || 0;
    if (remaining) {
        return '<span class="cell-status status-pending">剩 ' + remaining + ' 条</span>';
    }
    if (failed) {
        return '<span class="cell-status status-failed">失败 ' + failed + ' 条</span>';
    }
    return '<span class="cell-status status-done">已完成</span>';
}

function getChannelGroups(links) {
    var groups = [];  // 按频道分组下载链接,保持频道首次出现的顺序。
    var index = {};
    var i;
    for (i = 0; i < links.length; i++) {
        var channel = links[i].channel || UNGROUPED_NAME;
        if (index[channel] === undefined) {
            index[channel] = groups.length;
            groups.push({channel: channel, name: '', links: []});
        }
        var group = groups[index[channel]];
        var name = links[i].channel_name || channel;
        if (name.length > group.name.length) {
            group.name = name;  // 同一频道取信息最全的名称,"标题(ID)"比纯ID长。
        }
        group.links.push(links[i]);
    }
    for (i = 0; i < groups.length; i++) {
        var channelGroup = groups[i];
        channelGroup.count = channelGroup.links.length;
        channelGroup.complete = 0;
        channelGroup.member = 0;
        channelGroup.remaining = 0;
        channelGroup.failed = 0;
        channelGroup.members = [];  // 汇总该频道下所有链接的成员,用于计算频道级速度与剩余时间。
        for (var j = 0; j < channelGroup.links.length; j++) {
            channelGroup.complete += channelGroup.links[j].complete || 0;
            channelGroup.member += channelGroup.links[j].member || 0;
            channelGroup.remaining += channelGroup.links[j].remaining || 0;
            channelGroup.failed += channelGroup.links[j].failed || 0;
            channelGroup.members = channelGroup.members.concat(channelGroup.links[j].queue || []);
        }
        var base = channelGroup.member - channelGroup.failed;  // 彻底失败的成员退出进度基数,避免进度永远到不了100%。
        channelGroup.percent = base ?
            Math.round(channelGroup.complete / base * 1000) / 10 : 0;
    }
    return groups;
}

function channelBlock(group, live) {
    var key = 'channel:' + group.channel;
    var filtering = Boolean(statFilter.download);
    // 筛选时强制展开,避免结果被折叠状态藏起来。
    var isCollapsed = filtering ? false : (collapsed[key] === undefined ? allCollapsed : collapsed[key]);
    var stat = groupStat(group.members || [], live);
    var html = '<div class="group' + (isCollapsed ? '' : ' open') + '" data-channel="' + escAttr(key) + '" data-level="1">' +
        '<div class="group-head" data-channel="' + escAttr(key) + '">' +
        '<span class="cell-name"><span class="arrow"></span>' +
        '<span class="ficon">📺</span>' +
        '<span class="gname" title="' + escAttr(group.name || group.channel) + '">' +
        esc(group.name || group.channel) + '</span>' +
        '<span class="gcount">' + group.count + ' 个链接</span></span>' +
        progressCell(group.percent) +
        '<span class="cell-size">' + group.complete + '/' + group.member + '</span>' +
        groupStatCells(stat) +
        linkStatusCell(group) +
        '</div>' +
        '<div class="group-body"' + (isCollapsed ? ' style="display:none"' : '') + '>';
    var body = '';
    for (var i = 0; i < group.links.length; i++) {
        body += linkBlock(group.links[i], live);
    }
    if (filtering && !body) {
        return '';  // 筛选后该频道下没有任何匹配内容,整组不显示。
    }
    return html + body + '</div></div>';
}

function linkBlock(link, live) {
    var key = 'link:' + link.link;
    var filtering = Boolean(statFilter.download);
    var all = link.queue || [];
    var members = all;
    if (filtering) {
        members = all.filter(matchDownloadState);
        if (members.length === 0) {
            return '';  // 筛选后无匹配成员,不再显示该链接。
        }
    } else {
        // 无筛选卡片时按状态置顶:进行中 > 队列中 > 已完成/已跳过 > 失败,使活跃任务集中显示在最上方。
        members = members.slice().sort(function (a, b) {
            return stateRank(a.state) - stateRank(b.state);
        });
    }
    // 筛选时强制展开,否则结果会被折叠状态藏起来。
    var isCollapsed = filtering ? false : (collapsed[key] === undefined ? lastLinkCollapsed : collapsed[key]);
    var stat = groupStat(all, live);
    var html = '<div class="group' + (isCollapsed ? '' : ' open') + '" data-channel="' + escAttr(key) + '" data-level="2">' +
        '<div class="group-head" data-channel="' + escAttr(key) + '">' +
        '<span class="cell-name"><span class="arrow"></span>' +
        '<span class="ficon">🔗</span>' +
        '<span class="fname" title="' + escAttr(link.link) + '">' + esc(link.link) + '</span>' +
        '<span class="gcount">' + (link.queue_total || 0) + ' 条未完成 / 共 ' + (link.total || 0) + ' 条</span></span>' +
        progressCell(link.percent) +
        '<span class="cell-size">' + link.complete + '/' + link.member + '</span>' +
        groupStatCells(stat) +
        linkStatusCell(link) +
        '</div>' +
        '<div class="group-body"' + (isCollapsed ? ' style="display:none"' : '') + '>';
    for (var i = 0; i < members.length; i++) {
        var member = members[i];
        var task = member.state === 'downloading' ? live[member.task_id] : null;
        html += task ? taskRow(task) : memberRow(member);  // 下载中的成员直接复用进度条任务行。
    }
    if (members.length === 0) {
        html += '<div class="more">该链接暂无消息。</div>';
    }
    return html + '</div></div>';
}

function groupVisible(node) {
    for (var parent = node.parentNode; parent; parent = parent.parentNode) {
        if (parent.style && parent.style.display === 'none') {
            return false;  // 任一层祖先被折叠,该分组即不可见。
        }
    }
    return true;
}

function syncHeadLabel() {
    var level = 1;
    var nodes = document.querySelectorAll('#download .group.open');
    for (var i = 0; i < nodes.length; i++) {
        var depth = nodes[i].getAttribute('data-level') === '2' ? 3 : 2;
        if (depth > level && groupVisible(nodes[i])) {
            level = depth;  // 取当前可见的最深层级。
        }
    }
    document.getElementById('headName').querySelector('.htext').textContent = HEAD_LABELS[level - 1];
    document.getElementById('headSize').querySelector('.htext').textContent = SIZE_LABELS[level - 1];  // 分组行是条数,成员行才是字节。
}

function bindGroups() {
    // 只绑定下载页与上传页的分组条:记录页的分组条仅作归类展示,不参与折叠。
    var nodes = document.querySelectorAll('#download .group-head, #upload .group-head');
    for (var i = 0; i < nodes.length; i++) {
        nodes[i].onclick = function () {
            var group = this.parentNode;
            var key = this.getAttribute('data-channel');
            var body = group.querySelector('.group-body');
            var hide = body.style.display !== 'none';  // 当前是展开的,点击后折叠。
            body.style.display = hide ? 'none' : '';
            group.className = hide ? 'group' : 'group open';
            collapsed[key] = hide;
            saveState(COLLAPSE_KEY, JSON.stringify(collapsed));  // 记住本次折叠,刷新后恢复。
            if (group.getAttribute('data-level') === '2') {
                lastLinkCollapsed = hide;  // 下载页链接层的手动选择。
                saveState(LINK_LAST_KEY, hide ? '1' : '0');
            } else if (group.closest('#upload')) {
                lastUploadCollapsed = hide;  // 上传页频道层的手动选择。
                saveState(UPLOAD_LAST_KEY, hide ? '1' : '0');
            }
            syncHeadLabel();
            syncUploadHeads();
        };
    }
}

function syncToggleAll() {
    document.getElementById('toggleAll').textContent = allCollapsed ? '全部展开' : '全部折叠';
}

function syncToggleUpload() {
    document.getElementById('toggleUpload').textContent = uploadAllCollapsed ? '全部展开' : '全部折叠';
}

function setAllGroups(selector, hide) {
    var nodes = document.querySelectorAll(selector + ' .group');
    for (var i = 0; i < nodes.length; i++) {
        var key = nodes[i].getAttribute('data-channel');
        var body = nodes[i].querySelector('.group-body');
        body.style.display = hide ? 'none' : '';
        nodes[i].className = hide ? 'group' : 'group open';
        collapsed[key] = hide;
    }
    saveState(COLLAPSE_KEY, JSON.stringify(collapsed));  // 批量折叠后同样落盘,刷新后保持。
    if (selector === '#download') {
        lastLinkCollapsed = hide;  // 批量操作同样视为一次链接层选择。
        saveState(LINK_LAST_KEY, hide ? '1' : '0');
    } else {
        lastUploadCollapsed = hide;  // 批量操作同样视为一次频道层选择。
        saveState(UPLOAD_LAST_KEY, hide ? '1' : '0');
    }
}

function toggleAll() {
    allCollapsed = !allCollapsed;
    saveState(ALL_KEY, allCollapsed ? '1' : '0');
    setAllGroups('#download', allCollapsed);
    syncToggleAll();
    syncHeadLabel();
}

function toggleUploadAll() {
    uploadAllCollapsed = !uploadAllCollapsed;
    saveState(UPLOAD_ALL_KEY, uploadAllCollapsed ? '1' : '0');
    setAllGroups('#upload', uploadAllCollapsed);
    syncToggleUpload();
    syncUploadHeads();
}

function saveState(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch (e) {
        // 隐私模式下写入失败可忽略。
    }
}

function applySection() {
    var items = document.querySelectorAll('.side-item');
    for (var i = 0; i < items.length; i++) {
        var active = items[i].getAttribute('data-section') === currentSection;
        items[i].className = active ? 'side-item active' : 'side-item';
    }
    var dlWasHidden = document.getElementById('downloadSummary').hidden;
    var storageWasHidden = document.getElementById('page-storage').hidden;
    document.getElementById('downloadSummary').hidden = currentSection !== 'download';
    document.getElementById('uploadSummary').hidden = currentSection !== 'upload';  // 两个板块各自独立的总进度。
    for (i = 0; i < PAGES.length; i++) {
        document.getElementById('page-' + PAGES[i]).hidden = PAGES[i] !== currentSection;
    }
    renderStatus();
    // 下载总进度卡片刚变为可见时,用最新数据强制重绘一次进度条,
    // 避免首屏或切回下载页时它在隐藏态下渲染、进度条被跳过/未显示。
    if (currentSection === 'download' && dlWasHidden) {
        refresh(true);
    }
    if (currentSection === 'storage' && storageWasHidden) {
        refreshStorage();  // 记录页刚变为可见时立即拉取,避免展示上次的旧数据。
    }
}

function switchSection(name) {
    if (!SECTIONS[name]) {
        name = 'download';
    }
    if (!HAS_BOT && name !== 'download' && name !== 'storage') {  // 未配置机器人时仅允许下载页与记录页,避免停留在不可用的上传/监听页。
        name = 'download';
    }
    if (!HAS_STORAGE && name === 'storage') {  // 记录数据库不可用时回退下载页。
        name = 'download';
    }
    currentSection = name;
    applySection();
    saveState(SECTION_KEY, currentSection);
}

function applySectionVisibility() {
    // 上传与监听依赖机器人,未配置时隐藏这两个入口,避免用户点击后毫无反应。
    if (!HAS_BOT) {
        var botItems = document.querySelectorAll('.side-item[data-section="upload"], .side-item[data-section="listener"]');
        for (var i = 0; i < botItems.length; i++) {
            botItems[i].hidden = true;
        }
    }
    // 记录入口只在数据库可用时展示,不可用时隐藏,避免进入空页面。
    var storageItem = document.querySelector('.side-item[data-section="storage"]');
    if (storageItem) {
        storageItem.hidden = !HAS_STORAGE;
    }
    // 未配置机器人且记录不可用时只有下载一个功能,无需用侧边栏区分页面,直接隐藏整个侧边栏并将布局退化为单栏。
    if (HAS_BOT || HAS_STORAGE) {
        return;
    }
    var sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.hidden = true;
    }
    var layout = document.querySelector('.layout');
    if (layout && !layout.classList.contains('layout-single')) {
        layout.classList.add('layout-single');
    }
}

function applyListenTab() {
    var tabs = document.querySelectorAll('#listenTabs .tab');
    for (var i = 0; i < tabs.length; i++) {
        var active = tabs[i].getAttribute('data-listen') === currentListen;
        tabs[i].className = active ? 'tab active' : 'tab';
    }
    document.getElementById('listenForwardBox').hidden = currentListen !== 'forward';
    document.getElementById('listenDownloadBox').hidden = currentListen !== 'download';
}

function switchListen(name) {
    if (LISTEN_TABS.indexOf(name) === -1) {
        name = LISTEN_TABS[0];
    }
    currentListen = name;
    applyListenTab();
    saveState(LISTEN_KEY, currentListen);
}

function extraText(item) {
    var extra = '';
    if (item.speed) {
        extra += item.speed;
    }
    if (item.remaining) {
        extra += (extra ? ' · 剩余' : '剩余') + item.remaining;
    }
    return extra;
}

function renderOverall(summary, taskCount, ids) {
    var data = summary || EMPTY_SUMMARY;
    document.getElementById(ids.fill).style.width = data.percent + '%';
    document.getElementById(ids.percent).textContent = data.percent + '%';
    document.getElementById(ids.info).textContent = data.info;
    document.getElementById(ids.extra).textContent =
        extraText(data) ? extraText(data) : (taskCount ? '正在测速' : '暂无速度');
}

/* 统计卡筛选:点击后只显示对应状态的条目,再次点击取消。 */
var statFilter = {download: '', upload: ''};

// 筛选后无匹配项时的空态文案,与统计卡片的筛选口径保持一致。
var DOWNLOAD_EMPTY_TEXT = {
    success: '暂无成功的下载任务。',
    failure: '暂无失败的下载任务。',
    skip: '暂无跳过的下载任务。',
    active: '暂无下载中的任务。',
    queue: '暂无队列中的下载任务。'
};
var UPLOAD_EMPTY_TEXT = {
    success: '暂无上传成功的任务。',
    failure: '暂无上传失败的任务。',
    uploading: '暂无上传中的任务。',
    pending: '暂无队列中的上传任务。'
};

function statCell(label, value, cls, filter, scope) {
    if (!filter || !scope) {
        return '<div><span>' + label + '</span><b' + (cls ? ' class="' + cls + '"' : '') + '>' +
            value + '</b></div>';
    }
    var active = statFilter[scope] === filter;
    return '<div class="' + (active ? 'active ' : '') + '"' +
        ' data-filter="' + filter + '" data-scope="' + scope + '"' +
        ' title="点击' + (active ? '取消筛选' : '只查看' + label) + '">' +
        '<span>' + label + '</span><b' + (cls ? ' class="' + cls + '"' : '') + '>' +
        value + '</b></div>';
}

// 判断下载成员是否命中当前筛选。
function matchDownloadState(member) {
    var state = member.state || 'pending';
    var filter = statFilter.download;
    if (filter === 'success') {
        return state === 'success' || state === 'sent';
    }
    if (filter === 'failure') {
        return state === 'failure';
    }
    if (filter === 'skip') {
        return state === 'skip';
    }
    if (filter === 'active') {
        return state === 'downloading';
    }
    if (filter === 'queue') {
        return state === 'pending';
    }
    return true;
}

/* 统计"队列中"的成员数:只算排队中的,不含正在下载的。
   后端 data.queue 是"未完成总数"(含下载中),直接显示会导致队列数与进行中重复。 */
function countQueueMembers(links) {
    var total = 0;
    for (var i = 0; i < (links || []).length; i++) {
        var members = links[i].queue || [];
        for (var j = 0; j < members.length; j++) {
            var state = members[j].state || 'pending';
            if (state === 'pending') {
                total += 1;
            }
        }
    }
    return total;
}

// 判断上传文件是否命中指定筛选,与 uploadCount 的分类口径保持一致。
function matchUploadState(file, filter) {
    var state = file.state || 'pending';
    if (filter === 'success') {
        return uploadDone(file);
    }
    if (filter === 'failure') {
        return state === 'failure';
    }
    if (filter === 'uploading') {
        return !uploadDone(file) && state === 'uploading';
    }
    if (filter === 'pending') {
        return !uploadDone(file) && state !== 'failure' && state !== 'uploading';
    }
    return true;  // 文件总数等:不过滤。
}


function bindStatFilter() {
    document.addEventListener('click', function (event) {
        var cell = event.target && event.target.closest ? event.target.closest('[data-filter]') : null;
        if (!cell) {
            return;
        }
        var scope = cell.getAttribute('data-scope') || 'download';
        var value = cell.getAttribute('data-filter') || '';
        statFilter[scope] = statFilter[scope] === value ? '' : value;  // 再次点击取消筛选。
        // 筛选状态属于界面状态、不在快照数据里,必须清空指纹强制重绘,
        // 否则会因"数据未变化"被跳过,导致点击无反应。
        lastRenderKey = '';
        lastStructKey = null;
        lastUploadStructKey = null;
        refresh();  // 立即按新筛选重绘,无需等待下一次轮询。
    });
}

function renderStat(id, cells) {
    document.getElementById(id).innerHTML = cells.join('');
}

function renderStatus() {
    // 下载、上传、监听三个板块的活跃情况统一显示在顶栏左侧,不再跟随当前板块切换。
    var parts = [];
    if (lastPaused) {
        parts.push('已暂停');
    }
    if (lastDownloadActive) {
        parts.push('下载 ' + lastDownloadActive);
    }
    if (lastUploadActive) {
        parts.push('上传 ' + lastUploadActive);
    }
    if (lastListenCount) {
        parts.push('监听 ' + lastListenCount);
    }
    var active = parts.length > 0;
    document.getElementById('dot').className = active ? 'dot active' : 'dot';
    document.getElementById('statusText').textContent = active ? parts.join(' · ') : '空闲 · 等待任务';
}

function renderList(data) {
    var live = {};  // 进度条任务ID -> 任务,供下载中的成员复用实时进度。
    var i;
    for (i = 0; i < (data.tasks || []).length; i++) {
        live[data.tasks[i].id] = data.tasks[i];
    }
    var html = '';
    var groups = getChannelGroups(data.links || []);  // 频道 > 链接 > 下载信息,两级可折叠。
    for (i = 0; i < groups.length; i++) {
        html += channelBlock(groups[i], live);
    }
    /* 空态以"该链接下是否还有成员(含已完成的)"判断,而非"是否有正在下载的任务"。
       否则全部下载完成后 data.tasks 为空,已完成的成员会被空态整块隐藏,
       需新建任务才重新出现。 */
    // 处于筛选状态时,无匹配项应提示具体的筛选条件,而非笼统的"暂无下载任务。"。
    var emptyText = '暂无下载任务。';
    if (statFilter.download) {
        emptyText = DOWNLOAD_EMPTY_TEXT[statFilter.download] || emptyText;
    }
    document.getElementById('download').innerHTML = html ? html : '<div class="empty">' + emptyText + '</div>';
    syncToggleAll();
    bindGroups();  // 页面渲染完成后统一绑定折叠事件。
    syncHeadLabel();
}

function listenRow(kind, source, target) {
    var link = target ? source + ' ' + target : source;  // 与后端监听字典的键保持一致。
    var html = '<div class="task-row">' +
        '<span class="cell-name"><span class="ficon">🕵️</span>' +
        '<span class="fname" title="' + escAttr(source) + '">' + esc(source) + '</span></span>';
    if (target) {
        html += '<span class="cell-name"><span class="ficon">➡️</span>' +
            '<span class="fname" title="' + escAttr(target) + '">' + esc(target) + '</span></span>';
    }
    html += '<span class="cell-action"><button class="btn-del" type="button" title="移除该监听"' +
        ' data-kind="' + kind + '" data-link="' + escAttr(link) + '">✖</button></span>';
    return html + '</div>';
}

function renderListeners(listeners) {
    var data = listeners || {};
    var forward = data.forward || [];
    var download = data.download || [];
    var html = '';
    var i;
    for (i = 0; i < forward.length; i++) {
        html += listenRow('forward', forward[i].source, forward[i].target);
    }
    document.getElementById('listenForward').innerHTML = html ? html : '<div class="empty">暂无监听转发。</div>';
    html = '';
    for (i = 0; i < download.length; i++) {
        html += listenRow('download', download[i]);
    }
    document.getElementById('listenDownload').innerHTML = html ? html : '<div class="empty">暂无监听下载。</div>';
    return forward.length + download.length;
}

/* 记录页:展示数据库中的下载与上传历史。
   文件是否还存在由后端在读取时实时校验,不存在的条目已被丢弃,故前端只负责展示。
   扁平表格:频道与链接作为列,按频道、链接归类排序,同一归类内保持接口返回的新旧顺序。 */
var STORAGE_TABS = ['download', 'upload'];  // 记录页的选项卡:下载、上传。
var STORAGE_KEY = 'trmd_storage';  // 记录页选项卡的本地存储键。
var STORAGE_POLL_INTERVAL_MS = 3000;  // 记录页的轮询间隔,比进度页稀疏,避免频繁查询数据库。

var STORAGE_EMPTY_TEXT = {
    download: '暂无下载存储。',
    upload: '暂无上传存储。'
};
var currentStorage = 'download';
var STORAGE_TEXT = {
    success: '成功',
    skip: '已跳过',
    failure: '失败'
};
var STORAGE_CLASS = {
    success: 'status-done',
    skip: 'status-skip',
    failure: 'status-failed'
};
var STORAGE_ICON = {
    download: '📥',
    upload: '📤'
};
var STORAGE_UPLOAD_LINK = '本地上传';  // 上传存储没有下载链接,链接列统一显示该文案。
var STORAGE_HEADERS = {
    download: ['频道 / 消息', '文件', '链接', '大小', '消息ID', '类型', '状态', '时间'],
    upload:   ['频道', '文件路径', '大小', '类型', '状态', '时间']
};
var STORAGE_COLS = {
    download: '150px minmax(200px, 1fr) 200px 100px 90px 90px 90px 150px',
    upload:   '150px minmax(200px, 1fr) 100px 90px 90px 150px'
};

/* 筛选列定义:与STORAGE_HEADERS按序一一对应,kind决定筛选器类型(text文本/number数值/date日期)。
   列key对应storageFilterValue的取值逻辑,值列表与单元格展示同源,用户看到什么就筛什么。 */
var STORAGE_FILTER_COLS = {
    download: [
        {key: 'chat', kind: 'text'},
        {key: 'file', kind: 'text'},
        {key: 'link', kind: 'text'},
        {key: 'size', kind: 'number', unit: 'MB', arg: '输入大小(MB)'},
        {key: 'mid', kind: 'number'},
        {key: 'type', kind: 'text'},
        {key: 'state', kind: 'text'},
        {key: 'time', kind: 'date'}
    ],
    upload: [
        {key: 'chat', kind: 'text'},
        {key: 'path', kind: 'text'},
        {key: 'size', kind: 'number', unit: 'MB', arg: '输入大小(MB)'},
        {key: 'type', kind: 'text'},
        {key: 'state', kind: 'text'},
        {key: 'time', kind: 'date'}
    ]
};
var STORAGE_FILTER_OPS = {  // 自定义条件的运算符,按列类型分组。
    text: [
        {op: 'contains', label: '包含'},
        {op: 'equals', label: '等于'},
        {op: 'notEquals', label: '不等于'},
        {op: 'begins', label: '开头是'},
        {op: 'ends', label: '结尾是'}
    ],
    number: [
        {op: 'greater', label: '大于'},
        {op: 'less', label: '小于'},
        {op: 'equals', label: '等于'},
        {op: 'between', label: '介于'}
    ],
    date: [
        {op: 'equals', label: '等于'},
        {op: 'after', label: '晚于'},
        {op: 'before', label: '早于'},
        {op: 'between', label: '介于'}
    ]
};
var STORAGE_FILTER_CUSTOM_LABEL = {  // 面板里切换自定义条件的入口文案。
    text: '文本筛选',
    number: '数字筛选',
    date: '日期筛选'
};
var STORAGE_FILTER_ARG_LABEL = {  // 自定义条件输入框的占位符。
    text: '输入关键字',
    number: '输入数值',
    date: '输入日期(YYYY-MM-DD)'
};
var STORAGE_FILTER_EMPTY = {  // 筛选后无结果时的空态文案。
    download: '没有符合筛选条件的下载记录。',
    upload: '没有符合筛选条件的上传记录。'
};
var STORAGE_FILTER_KEY = 'trmd_storage_filters';  // 筛选条件的本地存储键,刷新后仍生效。
var FILTER_MB = 1024 * 1024;  // 大小列自定义条件按MB输入,保存时换算为字节与size_byte比较。
/* 表头筛选按钮图标:未筛选为下拉箭头,筛选中为漏斗,由CSS切换显隐。 */
var STORAGE_FILTER_ICONS =
    '<svg class="hfilter-arrow" width="10" height="6" viewBox="0 0 10 6" aria-hidden="true">' +
    '<path d="M1 1l4 4 4-4" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
    '<svg class="hfilter-funnel" width="11" height="10" viewBox="0 0 12 12" aria-hidden="true">' +
    '<path d="M1.5 2h9L7.6 6.6V10L4.4 8.4V6.6L1.5 2z" stroke="currentColor" stroke-width="1.3" fill="none" stroke-linejoin="round"/></svg>';
var storageFilters = {download: {}, upload: {}};  // 各选项卡独立保存筛选条件:列key -> {mode:'values',values} 或 {mode:'custom',op,value,value2}。
var storageFilterPop = null;  // 当前打开的筛选面板,同时只存在一个。
var storageFilterPanel = null;  // 面板打开期间的临时勾选状态,确定时才写回storageFilters,取消即丢弃。
var storageFilterCol = '';  // 面板正在筛选的列key。
var storageFilterInnerDown = false;  // 按下起点是否在面板内:排除输入框拖选文字时鼠标移出面板被误判为外点。

/* 按当前存储选项卡(下载/上传)重建表头、列宽与拖拽把手。
   下载保持原始 8 列(含链接、消息ID,按消息分组);上传为 6 列(无链接/消息ID,按频道分组)。 */
function applyStorageLayout() {
    var list = document.querySelector('.list-storage');
    if (!list) {
        return;
    }
    var head = list.querySelector('.list-head');
    if (!head) {
        return;
    }
    var headers = STORAGE_HEADERS[currentStorage] || STORAGE_HEADERS.download;
    var cols = STORAGE_FILTER_COLS[currentStorage] || STORAGE_FILTER_COLS.download;
    var html = '';
    for (var i = 0; i < headers.length; i++) {
        var active = cols[i] && storageFilters[currentStorage][cols[i].key] ? ' active' : '';
        html += '<span><span class="htext">' + esc(headers[i]) + '</span>' +
            '<button type="button" class="hfilter' + active + '" data-filter="' + cols[i].key + '" title="筛选">' +
            STORAGE_FILTER_ICONS + '</button></span>';
    }
    head.innerHTML = html;
    list.style.setProperty('--cols', STORAGE_COLS[currentStorage] || STORAGE_COLS.download);
    initCols();  // 按新列数与列宽重建拖拽把手;旧把手随 head.innerHTML 一并销毁,不会重复。
}

function applyStorageTab() {
    var tabs = document.querySelectorAll('#storageTabs .tab');
    for (var i = 0; i < tabs.length; i++) {
        var active = tabs[i].getAttribute('data-storage') === currentStorage;
        tabs[i].className = active ? 'tab active' : 'tab';
    }
    applyStorageLayout();  // 同步表头、列宽与拖拽把手到当前选项卡布局。
}

function switchStorage(name) {
    if (STORAGE_TABS.indexOf(name) === -1) {
        name = 'download';
    }
    closeStorageFilterPop();  // 表头即将重建,先关面板避免与新表头错位。
    currentStorage = name;
    applyStorageTab();
    saveState(STORAGE_KEY, currentStorage);
    storagePage.index = 0;  // 切换类型回到首页,避免停留在其他类型不存在的页号。
    refreshStorage();
}

function bindStorageTabs() {
    var tabs = document.querySelectorAll('#storageTabs .tab');
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].onclick = function () {
            switchStorage(this.getAttribute('data-storage'));
        };
    }
    var btn = document.getElementById('toggleStorage');
    if (btn) {
        btn.onclick = refreshStorage;  // 手动刷新按钮。
    }
}

/* 归类排序:先按频道、再按链接。
   同一链接(同一消息或同一条评论)内,下载按消息ID升序:评论记录的message_id即评论ID,
   故链接列呈现为从小到大;上传按记录ID降序。现代浏览器的Array.prototype.sort为稳定排序。 */
function sortStorage(storages) {
    return storages.slice().sort(function (a, b) {
        var chatA = a.chat || '';
        var chatB = b.chat || '';
        if (chatA !== chatB) {
            return chatA < chatB ? -1 : 1;
        }
        if (currentStorage !== 'upload') {
            var linkA = a.link || STORAGE_UPLOAD_LINK;
            var linkB = b.link || STORAGE_UPLOAD_LINK;
            if (linkA !== linkB) {
                return linkA < linkB ? -1 : 1;
            }
            return (Number(a.message_id) || 0) - (Number(b.message_id) || 0);  // 消息ID或评论ID升序。
        }
        var idA = Number(a.storage_id) || 0;
        var idB = Number(b.storage_id) || 0;
        return idB - idA;  // 上传:同频道内按记录ID降序,最新在前。
    });
}

/* 记录表是单层网格:第1列为纵向合并的频道单元格,第2~6列为每条存储的单元格。
   同一频道的所有记录归并为一个分组,频道名只显示一次并跨其所有行(Excel合并单元格的效果)。 */
function storageCell(column, row, cls, inner, title) {
    return '<div class="storage-cell' + cls + '" data-row="' + row + '"' +
        (title ? ' title="' + escAttr(title) + '"' : '') +
        ' style="grid-column:' + column + ';grid-row:' + row + '">' + inner + '</div>';
}

function storageGroupCell(group, startRow, len) {
    var first = group[0];
    var chat = first.chat || UNGROUPED_NAME;
    var badge = len > 1 ? '<span class="storage-msg-count">' + len + ' 个文件</span>' : '';
    var linkHtml = '';
    if (currentStorage !== 'upload') {
        var link = first.link || STORAGE_UPLOAD_LINK;  // 下载才有真实消息链接;上传无链接,显示"本地上传"。
        linkHtml = '<span class="storage-msg" title="' + escAttr(link) + '">' + esc(link) + '</span>';
    }
    return '<div class="storage-cell storage-channel-cell" style="grid-column:1;grid-row:' + startRow + ' / span ' + len + '">' +
        '<span class="fname" title="' + escAttr(chat) + '">' + esc(chat) + '</span>' +
        linkHtml +
        badge +
        '</div>';
}

/* 链接列展示成员自身链接:相册(媒体组)所有成员的记录共用整组任务链接(指向代表消息),
   把链接中的消息ID替换为本行的消息ID即可还原成员自己的链接。
   评论区链接带comment参数,该参数值即评论ID,同样替换为本行消息ID(评论区内媒体组同理)。
   无法识别的链接形态或无消息ID时保持原样,不做臆测改写。 */
function memberLink(rec) {
    var link = rec.link;
    if (!link) {
        return STORAGE_UPLOAD_LINK;  // 上传存储无链接,显示"本地上传"。
    }
    var mid = rec.message_id;
    if (mid === undefined || mid === null || mid === '') {
        return link;
    }
    // 普通消息链接:末尾一段为消息ID,替换为本行消息ID。
    var m = String(link).match(/^(.*\/)(\d+)$/);
    if (m) {
        return m[2] === String(mid) ? link : m[1] + mid;
    }
    // 评论区链接:comment参数值为评论ID,替换为本行消息ID。
    m = String(link).match(/^(.*[?&]comment=)(\d+)$/);
    if (m) {
        return m[2] === String(mid) ? link : m[1] + mid;
    }
    return link;  // 无法识别的形态保持原样。
}

function storageRowCells(item, row, position, groupStart) {
    var state = item.state || '';
    var text = STORAGE_TEXT[state] || item.status || '—';
    var cls = STORAGE_CLASS[state] || 'status-done';
    var extra = (groupStart ? ' group-start' : '') + (position % 2 ? ' alt' : '');
    var cells = '';
    // 第2列:下载显示文件名,上传显示完整文件路径(本地上传更关注路径)。
    var nameHtml = '<span class="ficon">' + (STORAGE_ICON[item.storage_type] || '📄') + '</span>';
    if (currentStorage !== 'upload') {
        nameHtml += '<span class="fname" title="' + escAttr(item.path || item.file) + '">' + esc(item.file) + '</span>';
    } else {
        nameHtml += '<span class="fname" title="' + escAttr(item.path || item.file) + '">' + esc(item.path || item.file) + '</span>';
    }
    cells += storageCell(2, row, extra + ' cell-name', nameHtml, item.path || item.file);
    if (currentStorage !== 'upload') {
        cells += storageCell(3, row, extra + ' cell-name',
            '<span class="fname">' + esc(memberLink(item)) + '</span>',
            memberLink(item));
        cells += storageCell(4, row, extra + ' cell-size', dash(item.size));
        cells += storageCell(5, row, extra + ' cell-speed', item.message_id ? esc(item.message_id) : '—');
        cells += storageCell(6, row, extra + ' cell-remain', dash(item.type));
        cells += storageCell(7, row, extra + ' cell-status ' + cls, esc(text), item.error);
        cells += storageCell(8, row, extra + ' cell-remain', dash(item.time));
    } else {
        cells += storageCell(3, row, extra + ' cell-size', dash(item.size));
        cells += storageCell(4, row, extra + ' cell-remain', dash(item.type));
        cells += storageCell(5, row, extra + ' cell-status ' + cls, esc(text), item.error);
        cells += storageCell(6, row, extra + ' cell-remain', dash(item.time));
    }
    return cells;
}

/* 记录结构指纹:记录ID + 状态,不含大小等展示字段。
   文件被删导致记录消失、或新记录写入时指纹变化,才重建列表。 */
function storageStructKey(storages) {
    var parts = [];
    for (var i = 0; i < storages.length; i++) {
        parts.push(storages[i].storage_id + '|' + storages[i].state);
    }
    return parts.join(';');
}

var lastStorageKey = null;  // 上次渲染的记录指纹,内容不变则跳过重建。(初始为 null 而非 '',否则无记录时指纹也是空串,会被误判为"未变化"导致空态永远不渲染)

function buildStorageRows(storages) {
    var groups = groupStorage(storages);  // 已按频道分组并排序。
    var html = '';
    var row = 1;  // 网格行号从1开始。
    var position = 0;  // 记录在整表中的序号,用于斑马纹。
    var g;
    var j;
    var items;
    for (g = 0; g < groups.length; g++) {
        items = groups[g];
        html += storageGroupCell(items, row, items.length);
        for (j = 0; j < items.length; j++) {
            html += storageRowCells(items[j], row + j, position, j === 0);
            position++;
        }
        row += items.length;
    }
    return html;
}

var storageAll = [];  // 当前类型的全量记录(已按服务器返回排序)。
var storagePage = {size: 100, index: 0};  // 分页状态:每页条数(0=不限)、当前页。

/* 记录分组键:按频道归类,同一频道的多条存储聚为一组(频道名跨行合并显示)。 */
function storageGroupKey(rec) {
    if (currentStorage !== 'upload') {
        if (rec.link) {
            return 'L:' + rec.link;
        }
        return 'U:' + (rec.path || ('id' + rec.storage_id));
    }
    return 'C:' + (rec.chat || UNGROUPED_NAME);
}

/* 组内最大 storage_id,用于组间排序(最新消息在前)。 */
function maxStorageId(arr) {
    var m = 0;
    for (var i = 0; i < arr.length; i++) {
        var id = Number(arr[i].storage_id) || 0;
        if (id > m) {
            m = id;
        }
    }
    return m;
}

/* 把记录按归类分组:下载按消息(链接)分组,上传按频道分组。
   组间一律按组内最大storage_id降序(最新在前),组内顺序由sortStorage决定。 */
function groupStorage(storages) {
    var sorted = sortStorage(storages);  // 先按频道归类排序,保证同一归类的记录相邻。
    var groups = [];
    var index = {};
    for (var i = 0; i < sorted.length; i++) {
        var key = storageGroupKey(sorted[i]);
        var g = index[key];
        if (g === undefined) {
            g = groups.length;
            index[key] = g;
            groups.push([]);
        }
        groups[g].push(sorted[i]);
    }
    groups.sort(function (a, b) {
        return maxStorageId(b) - maxStorageId(a);
    });
    return groups;
}

/* 按消息把记录切成连续块,供分页使用。 */
function messageBlocksOf(storages) {
    return groupStorage(storages);
}

/* 把消息块切分为页:尽量装到 page_size,但单个消息(相册)绝不跨页拆分;
   若某消息本身超过 page_size,则强制拉长当前页以完整显示它(下一页从该消息之后的消息开始)。 */
function paginateGroupBlocks(blocks, pageSize) {
    var pages = [];
    if (pageSize <= 0) {  // 不限:所有频道整块放入一页。
        var all = [];
        for (var k = 0; k < blocks.length; k++) {
            all = all.concat(blocks[k]);
        }
        if (all.length) {
            pages.push(all);
        }
        return pages;
    }
    var page = [];
    var count = 0;
    for (var i = 0; i < blocks.length; i++) {
        var block = blocks[i];
        if (count > 0 && count + block.length > pageSize) {
            pages.push(page);  // 放下一块会越界,先收尾本页,下一块从下一页开始。
            page = [];
            count = 0;
        }
        page = page.concat(block);  // 整块放入(若页为空且本块超长,则强制拉长本页)。
        count += block.length;
    }
    if (page.length) {
        pages.push(page);
    }
    return pages;
}

function pageStart(pages, index) {
    var offset = 0;
    for (var p = 0; p < index; p++) {
        offset += pages[p].length;
    }
    return pages.length ? offset + 1 : 0;
}

function pageEnd(pages, index) {
    if (!pages.length) {
        return 0;
    }
    var offset = 0;
    for (var p = 0; p <= index; p++) {
        offset += pages[p].length;
    }
    return offset;
}

function renderStorage(storages) {
    storageAll = storages;
    // 不在此重置页号:轮询刷新时保持用户所在页;切换类型/改每页条数时由对应动作重置。
    renderStoragePage();
}

/* 页面内容指纹:记录结构 + 页号 + 每页条数 + 当前tab。
   空态与非空态共用同一口径,确保切换tab后内容变化一定能触发重建。 */
function storagePageKey(pageStorages) {
    return storageStructKey(pageStorages) + '#' + storagePage.index + '#' + storagePage.size + '#' + currentStorage + '#' + storageFilterKey();
}

function renderStoragePage() {
    var filtered = filterStorage(storageAll);  // 筛选层:先按各列条件过滤,再走原有的分组与分页。
    var blocks = messageBlocksOf(filtered);
    var pages = paginateGroupBlocks(blocks, storagePage.size);
    var count = pages.length;
    var body = document.getElementById('storage');
    if (count === 0) {
        /* 空态也走指纹判定并回写lastStorageKey:否则切到空tab(如无记录的上传)再切回时,
           lastStorageKey仍停留在前一个tab的指纹,内容看似"未变化"而跳过重建,
           下载存储表会停留在空态,必须手动刷新才恢复。 */
        var emptyKey = storagePageKey([]);
        if (emptyKey !== lastStorageKey) {
            lastStorageKey = emptyKey;
            var emptyText = hasStorageFilter() ?
                (STORAGE_FILTER_EMPTY[currentStorage] || STORAGE_FILTER_EMPTY.download) :
                (STORAGE_EMPTY_TEXT[currentStorage] || STORAGE_EMPTY_TEXT.download);
            body.innerHTML = '<div class="empty">' + emptyText + '</div>';
        }
        document.getElementById('badgeStorage').textContent = storageAll.length;
        updateStoragePager(count, 0, filtered.length, blocks.length, 0, 0, storageAll.length);
        return;
    }
    if (storagePage.index >= count) {
        storagePage.index = count - 1;  // 数据变少时回退到末页。
    }
    if (storagePage.index < 0) {
        storagePage.index = 0;
    }
    var pageStorages = pages[storagePage.index];
    var key = storagePageKey(pageStorages);
    if (key !== lastStorageKey) {
        lastStorageKey = key;
        body.innerHTML = buildStorageRows(pageStorages);
    }
    document.getElementById('badgeStorage').textContent = storageAll.length;
    updateStoragePager(count, storagePage.index, filtered.length, blocks.length, pageStart(pages, storagePage.index), pageEnd(pages, storagePage.index), storageAll.length);
}

function updateStoragePager(count, index, shown, messages, start, end, total) {
    var pager = document.getElementById('storagePager');
    if (!pager) {
        return;
    }
    var cur = count ? index + 1 : 0;
    var curEl = pager.querySelector('.pager-cur');
    var totEl = pager.querySelector('.pager-total');
    var prev = document.getElementById('storagePrev');
    var next = document.getElementById('storageNext');
    var meta = document.getElementById('storagePagerMeta');
    if (curEl) {
        curEl.textContent = cur;
    }
    if (totEl) {
        totEl.textContent = count;
    }
    if (prev) {
        prev.disabled = (index <= 0);
    }
    if (next) {
        next.disabled = (index >= count - 1);
    }
    if (meta) {
        meta.textContent = (hasStorageFilter() ? '筛选后 ' + shown + ' 条 · 共 ' + total + ' 条' : '共 ' + total + ' 条') +
            ' · ' + messages + ' 个消息' + (count ? (' · 本页第 ' + start + '-' + end + ' 条') : '');
    }
}

function goStoragePage(delta) {
    storagePage.index += delta;
    renderStoragePage();
}

/* 同步每页条数下拉的显示值与高亮项,不触发渲染(供初始化使用)。 */
function applyPageSizeLabel(size) {
    var valEl = document.getElementById('storagePageSizeVal');
    if (valEl) {
        valEl.textContent = size === 0 ? '全部' : String(size);
    }
    var pop = document.getElementById('storagePageSizePop');
    if (pop) {
        var opts = pop.querySelectorAll('.pager-select-opt');
        for (var i = 0; i < opts.length; i++) {
            var s = parseInt(opts[i].getAttribute('data-size'), 10);
            opts[i].classList.toggle('active', s === size);
        }
    }
}

function setStoragePageSize(size) {
    storagePage.size = size;
    storagePage.index = 0;  // 改变每页条数回到首页。
    saveState('storagePageSize', size);
    applyPageSizeLabel(size);
    renderStoragePage();
}

function bindStoragePager() {
    var prev = document.getElementById('storagePrev');
    var next = document.getElementById('storageNext');
    var wrap = document.getElementById('storagePageSize');
    var btn = document.getElementById('storagePageSizeBtn');
    var pop = document.getElementById('storagePageSizePop');
    if (prev) {
        prev.onclick = function () { goStoragePage(-1); };
    }
    if (next) {
        next.onclick = function () { goStoragePage(1); };
    }
    if (wrap && btn && pop) {
        var saved = parseInt(localStorage.getItem('storagePageSize'), 10);
        if (!isNaN(saved) && (saved === 0 || (saved >= 20 && saved <= 500))) {
            storagePage.size = saved;  // 仅在合法范围内恢复,避免脏值。
        }
        applyPageSizeLabel(storagePage.size);  // 仅同步显示,不触发渲染。
        btn.onclick = function (event) {
            event.stopPropagation();
            pop.hidden = !pop.hidden;
            wrap.classList.toggle('open', !pop.hidden);
        };
        var opts = pop.querySelectorAll('.pager-select-opt');
        for (var i = 0; i < opts.length; i++) {
            opts[i].onclick = function (event) {
                event.stopPropagation();
                setStoragePageSize(parseInt(this.getAttribute('data-size'), 10));
                pop.hidden = true;
                wrap.classList.remove('open');
            };
        }
        document.addEventListener('click', function (event) {
            if (wrap.contains(event.target)) {
                return;
            }
            pop.hidden = true;
            wrap.classList.remove('open');
        });
    }
}

/* Excel式列筛选:在分组与分页之前插入过滤层,无筛选条件时恒等返回,现有链路一行不动。
   每列条件独立保存,多列之间为AND;值列表与计数只反映其他列筛选后的可见记录。 */
function hasStorageFilter() {
    return Object.keys(storageFilters[currentStorage]).length > 0;
}

/* 字节数转可读大小:与后端MetaData.suitable_units_display的十进制口径一致(如1.50MB),
   供大小列筛选值列表显示,保证用户看到的就是筛出来的。 */
function suitableSizeText(byte) {
    var units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    var values = [Number(byte) || 0];
    var i;
    for (i = 0; i < units.length - 1; i++) {
        if (values[i] >= 1000) {
            values.push(values[i] / 1000);
        } else {
            break;
        }
    }
    return values[values.length - 1].toFixed(2) + units[values.length - 1];
}

/* 筛选取值(原始值):与单元格展示同源,合并单元格的频道列取频道名,链接列取memberLink处理后的链接,
   大小列取字节数、消息ID取数字,供自定义条件做数值比较。 */
function storageFilterValue(rec, key) {
    if (key === 'chat') {
        return rec.chat || UNGROUPED_NAME;
    }
    if (key === 'file') {
        return rec.file || '';
    }
    if (key === 'path') {
        return rec.path || rec.file || '';
    }
    if (key === 'link') {
        return memberLink(rec);
    }
    if (key === 'size') {
        return Number(rec.size_byte) || 0;
    }
    if (key === 'mid') {
        return rec.message_id ? Number(rec.message_id) : 0;
    }
    if (key === 'type') {
        return rec.type || '';
    }
    if (key === 'state') {
        return STORAGE_TEXT[rec.state] || rec.status || '';
    }
    if (key === 'time') {
        return rec.time || '';
    }
    return '';
}

/* 筛选展示文本:与单元格最终显示一致,空值按破折号呈现,大小列按十进制单位格式化。 */
function storageFilterText(rec, key) {
    if (key === 'size') {
        return suitableSizeText(rec.size_byte);
    }
    if (key === 'mid') {
        return rec.message_id ? String(rec.message_id) : '—';
    }
    var value = storageFilterValue(rec, key);
    return value === '' ? '—' : String(value);
}

function storageFilterColDef(key) {
    var cols = STORAGE_FILTER_COLS[currentStorage] || [];
    for (var i = 0; i < cols.length; i++) {
        if (cols[i].key === key) {
            return cols[i];
        }
    }
    return null;
}

function storageFilterKind(key) {
    var col = storageFilterColDef(key);
    return col ? col.kind : 'text';
}

function defaultFilterOp(kind) {
    var ops = STORAGE_FILTER_OPS[kind] || STORAGE_FILTER_OPS.text;
    return ops[0].op;
}

/* 过滤层:各列条件求交集,任一列不满足即淘汰;无条件时原样返回。 */
function filterStorage(storages) {
    var filters = storageFilters[currentStorage];
    var keys = Object.keys(filters);
    if (!keys.length) {
        return storages;
    }
    return storages.filter(function (rec) {
        for (var i = 0; i < keys.length; i++) {
            if (!matchStorageFilter(rec, keys[i], filters[keys[i]])) {
                return false;
            }
        }
        return true;
    });
}

function matchStorageFilter(rec, key, cond) {
    if (cond.mode === 'custom') {
        return matchCustomFilter(storageFilterValue(rec, key), storageFilterKind(key), cond);
    }
    var values = cond.values || [];
    return values.indexOf(storageFilterText(rec, key)) !== -1;
}

/* 自定义条件匹配:文本忽略大小写,数值按字节数比较,日期按时间字符串字典序比较。 */
function matchCustomFilter(value, kind, cond) {
    var op = cond.op;
    if (kind === 'number') {
        var num = Number(value) || 0;
        if (op === 'between') {
            return num >= (Number(cond.value) || 0) && num <= (Number(cond.value2) || 0);
        }
        if (op === 'equals') {
            return num === (Number(cond.value) || 0);
        }
        if (op === 'greater') {
            return num > (Number(cond.value) || 0);
        }
        if (op === 'less') {
            return num < (Number(cond.value) || 0);
        }
        return true;
    }
    if (kind === 'date') {
        var text = String(value);
        var from = String(cond.value || '');
        var to = String(cond.value2 || '');
        if (op === 'equals') {
            return text.indexOf(from) === 0;  // 日期前缀匹配:'2026-10-15'即可匹配当天全部记录。
        }
        if (op === 'after') {
            return text > from;
        }
        if (op === 'before') {
            return text < from;
        }
        if (op === 'between') {
            return to ? (text >= from && text <= to + ' 23:59:59') : text >= from;
        }
        return true;
    }
    var target = String(value).toLowerCase();
    var query = String(cond.value || '').toLowerCase();
    if (op === 'equals') {
        return target === query;
    }
    if (op === 'notEquals') {
        return target !== query;
    }
    if (op === 'contains') {
        return target.indexOf(query) !== -1;
    }
    if (op === 'notContains') {
        return target.indexOf(query) === -1;
    }
    if (op === 'begins') {
        return target.indexOf(query) === 0;
    }
    if (op === 'ends') {
        return query.length > 0 && target.length >= query.length &&
            target.lastIndexOf(query) === target.length - query.length;
    }
    return true;
}

/* 某列的值统计:只统计其他列筛选后的可见记录,与Excel的上下文计数行为一致。
   数值列同时保留原始值作排序键,避免按显示文本排序时出现'10.00MB'排在'2.00MB'前的问题。 */
function storageValueCounts(key) {
    var filters = storageFilters[currentStorage];
    var keys = Object.keys(filters);
    var entries = {};
    for (var i = 0; i < storageAll.length; i++) {
        var rec = storageAll[i];
        var visible = true;
        for (var j = 0; j < keys.length; j++) {
            if (keys[j] !== key && !matchStorageFilter(rec, keys[j], filters[keys[j]])) {
                visible = false;
                break;
            }
        }
        if (!visible) {
            continue;
        }
        var text = storageFilterText(rec, key);
        if (entries[text] === undefined) {
            entries[text] = {count: 0, raw: storageFilterValue(rec, key)};
        }
        entries[text].count++;
    }
    return entries;
}

/* 筛选条件的序列化指纹:条件变化必须触发重建,否则内容看似未变而跳过渲染。 */
function storageFilterKey() {
    var filters = storageFilters[currentStorage];
    var keys = Object.keys(filters).sort();
    var parts = [];
    for (var i = 0; i < keys.length; i++) {
        var cond = filters[keys[i]];
        if (cond.mode === 'custom') {
            parts.push(keys[i] + ':' + cond.op + ':' + cond.value + ':' + cond.value2);
        } else {
            parts.push(keys[i] + ':' + (cond.values || []).join(','));
        }
    }
    return parts.join(';');
}

function saveStorageFilters() {
    saveState(STORAGE_FILTER_KEY, JSON.stringify(storageFilters));
}

/* 恢复上次的筛选条件:逐项校验结构与列key,脏数据整项丢弃,避免损坏的本地存储拖垮记录页。 */
function loadStorageFilters() {
    var saved = {};
    try {
        saved = JSON.parse(localStorage.getItem(STORAGE_FILTER_KEY) || '{}') || {};
    } catch (e) {
        saved = {};
    }
    var tabs = ['download', 'upload'];
    for (var t = 0; t < tabs.length; t++) {
        var tab = tabs[t];
        var cols = STORAGE_FILTER_COLS[tab] || [];
        var src = saved[tab];
        var dst = {};
        if (src && typeof src === 'object') {
            for (var i = 0; i < cols.length; i++) {
                var key = cols[i].key;
                var cond = src[key];
                if (!cond || typeof cond !== 'object') {
                    continue;
                }
                if (cond.mode === 'custom') {
                    if (typeof cond.value === 'string' && cond.value !== '') {
                        dst[key] = {
                            mode: 'custom',
                            op: String(cond.op || 'contains'),
                            value: cond.value,
                            value2: String(cond.value2 || '')
                        };
                    }
                } else if (cond.mode === 'values' && Object.prototype.toString.call(cond.values) === '[object Array]') {
                    var values = [];
                    for (var j = 0; j < cond.values.length; j++) {
                        values.push(String(cond.values[j]));
                    }
                    dst[key] = {mode: 'values', values: values};
                }
            }
        }
        storageFilters[tab] = dst;
    }
}

/* 同步表头筛选按钮的激活态:有条件的列显示漏斗并高亮,不改动表头结构。 */
function refreshStorageFilterButtons() {
    var buttons = document.querySelectorAll('.list-storage .list-head .hfilter');
    for (var i = 0; i < buttons.length; i++) {
        var key = buttons[i].getAttribute('data-filter');
        buttons[i].classList.toggle('active', !!storageFilters[currentStorage][key]);
    }
}

/* 把面板临时状态写回筛选条件并重渲染;无有效条件时视为清除该列筛选。 */
function commitStorageFilterPanel() {
    var panel = storageFilterPanel;
    var pop = storageFilterPop;
    var customView = pop ? pop.querySelector('.hfilter-custom') : null;
    var cond = null;
    if (panel.matchCustom && customView && customView.hidden) {
        // 以自定义条件打开且未进入自定义编辑视图:值列表勾选仅作展示,确定即保持原条件,不降级为values。
        cond = storageFilters[currentStorage][storageFilterCol];
    } else if (customView && !customView.hidden && panel.custom.value !== '') {
        var col = storageFilterColDef(storageFilterCol);
        var value = panel.custom.value;
        var value2 = panel.custom.value2;
        if (col && col.unit === 'MB') {  // 大小列按MB输入,换算为字节后与size_byte比较。
            value = String((Number(value) || 0) * FILTER_MB);
            value2 = String((Number(value2) || 0) * FILTER_MB);
        }
        cond = {mode: 'custom', op: panel.custom.op, value: value, value2: value2};
    } else if (panel.values && panel.values.length &&
        !sameStorageFilterValues(panel.values, panel.all || [])) {
        // 勾选值与全量可见值一致时等同于本列无筛选,不写回条件,图标恢复箭头。
        cond = {mode: 'values', values: panel.values.slice()};
    }
    if (cond) {
        storageFilters[currentStorage][storageFilterCol] = cond;
    } else {
        delete storageFilters[currentStorage][storageFilterCol];
    }
    saveStorageFilters();
    closeStorageFilterPop();
    refreshStorageFilterButtons();
    storagePage.index = 0;  // 条件变化回到首页,避免停留在已不存在的页号。
    renderStoragePage();
}

function closeStorageFilterPop() {
    if (storageFilterPop) {
        storageFilterPop.parentNode.removeChild(storageFilterPop);
    }
    storageFilterPop = null;
    storageFilterPanel = null;
    storageFilterCol = '';
}

/* 打开某列的筛选面板:复制当前条件为临时状态,确定才写回,取消或面板外点击即丢弃。 */
function openStorageFilterPop(button) {
    closeStorageFilterPop();
    var key = button.getAttribute('data-filter');
    storageFilterCol = key;
    var cond = storageFilters[currentStorage][key];
    if (cond && cond.mode === 'custom') {
        storageFilterPanel = {
            values: null,  // 由fillStorageFilterValues按custom条件匹配回填。
            custom: {op: cond.op, value: cond.value, value2: cond.value2 || ''},
            matchCustom: true  // 打开时按自定义条件勾选值列表,让勾选反映当前筛选涉及的值。
        };
    } else {
        storageFilterPanel = {
            values: cond && cond.values ? cond.values.slice() : null,  // null表示全选(无筛选)。
            custom: {op: defaultFilterOp(storageFilterKind(key)), value: '', value2: ''}
        };
    }
    var pop = buildStorageFilterPop();
    storageFilterPop = pop;
    document.body.appendChild(pop);
    fillStorageFilterValues(pop);
    placeStorageFilterPop(pop, button);
    bindStorageFilterPop(pop);
}

function buildStorageFilterPop() {
    var kind = storageFilterKind(storageFilterCol);
    var col = storageFilterColDef(storageFilterCol);
    var ops = STORAGE_FILTER_OPS[kind] || STORAGE_FILTER_OPS.text;
    var argLabel = (col && col.arg) || STORAGE_FILTER_ARG_LABEL[kind] || STORAGE_FILTER_ARG_LABEL.text;
    var pop = document.createElement('div');
    pop.className = 'hfilter-pop';
    var html = '';
    html += '<div class="hfilter-search"><input type="text" class="hfilter-search-input" placeholder="搜索"></div>';
    html += '<div class="hfilter-list">';
    html += '<label class="hfilter-item hfilter-all-item"><input type="checkbox" class="hfilter-all-box">' +
        '<span class="hfilter-label">(全选)</span></label>';
    html += '<div class="hfilter-values"></div>';
    html += '<div class="hfilter-none" hidden>无匹配值</div>';
    html += '</div>';
    html += '<div class="hfilter-custom" hidden>';
    // 运算符下拉复用每页条数的自定义下拉结构(.pager-select),不用浏览器原生select。
    html += '<div class="pager-select hfilter-op">' +
        '<button type="button" class="pager-select-btn hfilter-op-btn">' +
        '<span class="pager-select-val hfilter-op-val"></span>' +
        '<span class="pager-select-caret"></span>' +
        '</button>' +
        '<div class="pager-select-pop hfilter-op-pop" hidden>';
    for (var i = 0; i < ops.length; i++) {
        html += '<button type="button" class="pager-select-opt" data-op="' + escAttr(ops[i].op) + '">' + esc(ops[i].label) + '</button>';
    }
    html += '</div></div>';
    html += '<div class="hfilter-args">' +
        '<input type="text" class="hfilter-arg" placeholder="' + escAttr(argLabel) + '">' +
        '<input type="text" class="hfilter-arg hfilter-arg2" placeholder="至" hidden>' +
        '</div>';
    html += '</div>';
    html += '<div class="hfilter-switch">' +
        '<button type="button" class="hfilter-custom-btn">' + esc(STORAGE_FILTER_CUSTOM_LABEL[kind]) + '</button></div>';
    html += '<div class="hfilter-foot">' +
        '<button type="button" class="hfilter-ok">确定</button>' +
        '<button type="button" class="hfilter-cancel">取消</button></div>';
    pop.innerHTML = html;
    return pop;
}

/* 同步运算符自定义下拉的显示值与选中态:显示文本取对应选项的标签。 */
function syncFilterOpDisplay(pop, op) {
    var val = pop.querySelector('.hfilter-op-val');
    var opts = pop.querySelectorAll('.hfilter-op-pop .pager-select-opt');
    var label = op;
    for (var i = 0; i < opts.length; i++) {
        var match = opts[i].getAttribute('data-op') === op;
        opts[i].classList.toggle('active', match);
        if (match) {
            label = opts[i].textContent;
        }
    }
    if (val) {
        val.textContent = label;
    }
}

/* 填充值列表:数值列按原始值排序,其余按展示文本排序;values为null(无筛选)时默认全选。 */
function fillStorageFilterValues(pop) {
    var valuesBox = pop.querySelector('.hfilter-values');
    var entries = storageValueCounts(storageFilterCol);
    var kind = storageFilterKind(storageFilterCol);
    var values = Object.keys(entries);
    values.sort(function (a, b) {
        if (kind === 'number') {
            return (Number(entries[a].raw) || 0) - (Number(entries[b].raw) || 0);
        }
        return a < b ? -1 : (a > b ? 1 : 0);
    });
    var panel = storageFilterPanel;
    panel.all = values.slice();  // 打开时的全量可见值集,复原(全部勾上)时据此判定为无筛选。
    if (panel.values === null) {
        if (panel.matchCustom && panel.custom) {
            // 自定义条件打开:按条件逐值匹配回填勾选(复用记录级同一套matchCustomFilter),
            // 让值列表反映当前筛选涉及的值;匹配不到任何值时全不勾。
            var matched = [];
            for (var i = 0; i < values.length; i++) {
                if (matchCustomFilter(entries[values[i]].raw, kind, panel.custom)) {
                    matched.push(values[i]);
                }
            }
            panel.values = matched;
        } else {
            panel.values = values.slice();  // 无筛选:打开即全选。
        }
    }
    var html = '';
    for (var i = 0; i < values.length; i++) {
        var value = values[i];
        var checked = panel.values.indexOf(value) !== -1 ? ' checked' : '';
        html += '<label class="hfilter-item" data-value="' + escAttr(value) + '" data-label="' + escAttr(value.toLowerCase()) + '">' +
            '<input type="checkbox"' + checked + '>' +
            '<span class="hfilter-label" title="' + escAttr(value) + '">' + esc(value) + '</span>' +
            '<span class="hfilter-count">' + entries[value].count + '</span></label>';
    }
    valuesBox.innerHTML = html;
    pop.querySelector('.hfilter-none').hidden = values.length > 0;
    syncStorageFilterAllBox(pop);
}

/* (全选)复选框的三态:全勾选中、部分选中显示半选,与Excel一致。 */
function syncStorageFilterAllBox(pop) {
    var allBox = pop.querySelector('.hfilter-all-box');
    var items = pop.querySelectorAll('.hfilter-values .hfilter-item');
    var shown = 0;
    var checked = 0;
    for (var i = 0; i < items.length; i++) {
        if (items[i].hidden) {
            continue;
        }
        shown++;
        if (items[i].querySelector('input').checked) {
            checked++;
        }
    }
    allBox.checked = shown > 0 && checked === shown;
    allBox.indeterminate = checked > 0 && checked < shown;
}

/* 增删面板临时状态中的一个值。 */
function setStorageFilterValue(value, checked) {
    var values = storageFilterPanel.values;
    var at = values.indexOf(value);
    if (checked && at === -1) {
        values.push(value);
    } else if (!checked && at !== -1) {
        values.splice(at, 1);
    }
}

/* 勾选值与全量可见值完全一致:顺序无关,逐项比对。 */
function sameStorageFilterValues(selected, all) {
    if (selected.length !== all.length) {
        return false;
    }
    var a = selected.slice().sort();
    var b = all.slice().sort();
    for (var i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) {
            return false;
        }
    }
    return true;
}

/* 切换搜索后可见项的勾选态:(全选)只作用于当前可见项,隐藏项保持原状。 */
function toggleStorageFilterVisible(pop, checked) {
    var items = pop.querySelectorAll('.hfilter-values .hfilter-item');
    for (var i = 0; i < items.length; i++) {
        if (items[i].hidden) {
            continue;
        }
        items[i].querySelector('input').checked = checked;
        setStorageFilterValue(items[i].getAttribute('data-value'), checked);
    }
    syncStorageFilterAllBox(pop);
}

/* 面板定位:fixed避开表头滚动裁剪,右溢出时改为右对齐,小屏限制最大宽度。 */
function placeStorageFilterPop(pop, button) {
    var rect = button.getBoundingClientRect();
    var width = pop.offsetWidth;
    var left = rect.left;
    if (left + width > window.innerWidth - 8) {
        left = window.innerWidth - width - 8;
    }
    if (left < 8) {
        left = 8;
    }
    pop.style.left = left + 'px';
    pop.style.top = (rect.bottom + 6) + 'px';
}

function bindStorageFilterPop(pop) {
    var panel = storageFilterPanel;
    var search = pop.querySelector('.hfilter-search-input');
    var valuesBox = pop.querySelector('.hfilter-values');
    var none = pop.querySelector('.hfilter-none');
    var allBox = pop.querySelector('.hfilter-all-box');
    var customView = pop.querySelector('.hfilter-custom');
    var opWrap = pop.querySelector('.hfilter-op');
    var opBtn = pop.querySelector('.hfilter-op-btn');
    var opPop = pop.querySelector('.hfilter-op-pop');
    var argInput = pop.querySelector('.hfilter-arg');
    var arg2Input = pop.querySelector('.hfilter-arg2');
    var customBtn = pop.querySelector('.hfilter-custom-btn');
    search.addEventListener('input', function () {
        var query = this.value.trim().toLowerCase();
        var shown = 0;
        var items = valuesBox.querySelectorAll('.hfilter-item');
        for (var i = 0; i < items.length; i++) {
            var label = items[i].getAttribute('data-label') || '';
            items[i].hidden = query !== '' && label.indexOf(query) === -1;
            if (!items[i].hidden) {
                shown++;
            }
        }
        none.hidden = shown > 0;
        // 输入即筛选:有关键字时勾选与可见项完全一致(符合条件即选中,不符合的取消),
        // 搜索后直接确定即为该条件;清空关键字时保持原勾选不动,避免误伤打开时的条件。
        if (query !== '') {
            for (var i = 0; i < items.length; i++) {
                var visible = !items[i].hidden;
                var box = items[i].querySelector('input');
                if (box && box.checked !== visible) {
                    box.checked = visible;
                    setStorageFilterValue(items[i].getAttribute('data-value'), visible);
                }
            }
        }
        syncStorageFilterAllBox(pop);
    });
    allBox.addEventListener('change', function () {
        toggleStorageFilterVisible(pop, this.checked);
    });
    valuesBox.addEventListener('change', function (event) {
        var item = event.target.closest ? event.target.closest('.hfilter-item') : null;
        if (item) {
            setStorageFilterValue(item.getAttribute('data-value'), event.target.checked);
            syncStorageFilterAllBox(pop);
        }
    });
    syncFilterOpDisplay(pop, panel.custom.op);  // 初始显示当前运算符。
    opBtn.addEventListener('click', function (event) {
        event.stopPropagation();
        opPop.hidden = !opPop.hidden;
        opWrap.classList.toggle('open', !opPop.hidden);
    });
    var opOpts = opPop.querySelectorAll('.pager-select-opt');
    for (var i = 0; i < opOpts.length; i++) {
        opOpts[i].addEventListener('click', function (event) {
            event.stopPropagation();
            panel.custom.op = this.getAttribute('data-op');
            arg2Input.hidden = panel.custom.op !== 'between';
            syncFilterOpDisplay(pop, panel.custom.op);
            opPop.hidden = true;
            opWrap.classList.remove('open');
        });
    }
    argInput.addEventListener('input', function () {
        panel.custom.value = this.value.trim();
    });
    arg2Input.addEventListener('input', function () {
        panel.custom.value2 = this.value.trim();
    });
    // 筛选输入时每输入一个字符也推进背景涂鸦渐变,与登录框、修改配置弹窗一致(复用官方推进逻辑)。
    var filterAdvance = function () {
        if (!bgCtx) {
            return;  // 渐变背景未初始化成功时跳过。
        }
        bgAdvancePosition();
    };
    search.addEventListener('input', filterAdvance);
    argInput.addEventListener('input', filterAdvance);
    arg2Input.addEventListener('input', filterAdvance);
    customBtn.addEventListener('click', function () {
        if (customView.hidden) {
            // 值列表视图:进入自定义视图(保留设置自定义条件的入口)。
            customView.hidden = false;
            customBtn.textContent = '重置';
            syncFilterOpDisplay(pop, panel.custom.op);
            argInput.value = panel.custom.value;
            arg2Input.value = panel.custom.value2;
            arg2Input.hidden = panel.custom.op !== 'between';
            argInput.focus();
        } else {
            // 自定义视图:重置=清除该列筛选,等同在此条目勾选(全选)。
            delete storageFilters[currentStorage][storageFilterCol];
            saveStorageFilters();
            closeStorageFilterPop();
            refreshStorageFilterButtons();
            storagePage.index = 0;
            renderStoragePage();
        }
    });
    pop.querySelector('.hfilter-ok').addEventListener('click', function () {
        commitStorageFilterPanel();
    });
    pop.querySelector('.hfilter-cancel').addEventListener('click', function () {
        closeStorageFilterPop();
    });
    pop.addEventListener('click', function (event) {
        event.stopPropagation();  // 面板内点击不触发外部的关闭逻辑。
        if (opWrap && !opWrap.contains(event.target)) {  // 点击面板其他区域时收起运算符下拉。
            opPop.hidden = true;
            opWrap.classList.remove('open');
        }
    });
    // 已是自定义条件的列:打开面板直接进入自定义视图并回填,与值列表视图可随时互切。
    var cond = storageFilters[currentStorage][storageFilterCol];
    if (cond && cond.mode === 'custom') {
        customView.hidden = false;
        customBtn.textContent = '重置';  // 当前已在自定义视图,按钮语义为放弃自定义条件回到值列表。
        syncFilterOpDisplay(pop, panel.custom.op);
        argInput.value = panel.custom.value;
        arg2Input.value = panel.custom.value2;
        arg2Input.hidden = panel.custom.op !== 'between';
    }
}

/* 表头筛选入口:按钮由applyStorageLayout动态生成,用委托统一绑定,表头重建后依然有效。 */
function bindStorageFilters() {
    var list = document.querySelector('.list-storage');
    if (!list) {
        return;
    }
    list.addEventListener('click', function (event) {
        var button = event.target.closest ? event.target.closest('.hfilter') : null;
        if (!button) {
            return;
        }
        event.stopPropagation();  // 阻止冒泡到document,否则刚打开的面板会被"面板外点击"立刻关掉。
        openStorageFilterPop(button);
    });
    document.addEventListener('mousedown', function (event) {
        // 记录按下起点是否在面板内:输入框拖选文字时按住不放移出面板,松手时click的
        // target是共同祖先( document 级),不记录起点会把面板误关。
        storageFilterInnerDown = !!(storageFilterPop && storageFilterPop.contains(event.target));
    });
    document.addEventListener('click', function () {
        if (storageFilterInnerDown) {
            return;  // 从面板内开始的拖拽(如选字),松手即使在外面也不关闭。
        }
        closeStorageFilterPop();  // 面板外点击等同取消,临时勾选状态丢弃。
    });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            closeStorageFilterPop();
        }
    });
    var scroll = list.querySelector('.list-scroll');
    if (scroll) {
        scroll.addEventListener('scroll', function () {
            closeStorageFilterPop();  // 表头滚出视野时关闭面板,避免面板与按钮错位。
        });
    }
}

/* 整行悬停:记录行没有行容器,按所在网格行号给同一行的单元格加高亮。 */
function bindStorageHover() {
    var box = document.getElementById('storage');
    if (!box) {
        return;
    }
    var setRowHover = function (node, enable) {
        var cell = node && node.closest ? node.closest('.storage-cell[data-row]') : null;
        if (!cell || !box.contains(cell)) {
            return;
        }
        var cells = box.querySelectorAll('.storage-cell[data-row="' + cell.getAttribute('data-row') + '"]');
        for (var i = 0; i < cells.length; i++) {
            cells[i].classList.toggle('hover', enable);
        }
    };
    box.addEventListener('mouseover', function (event) {
        setRowHover(event.target, true);
    });
    box.addEventListener('mouseout', function (event) {
        setRowHover(event.target, false);
    });
}

async function refreshStorage() {
    refreshStorageDisk();  // 磁盘卡片与列表解耦,单独拉取,失败不影响列表。
    try {
        var res = await fetch('/api/storage?type=' + encodeURIComponent(currentStorage), {cache: 'no-store', headers: authHeaders()});
        if (res.status === 401) {
            openLogin();  // 未认证:弹出登录卡片,与进度页一致。
            return;
        }
        var json = await res.json();
        renderStorage(json.storage || []);
    } catch (e) {
        // 拉取失败时保留原列表,交由进度页的断线提示统一反馈。
    }
}

/* 拉取并渲染存储页的磁盘空间卡片:展示下载保存目录所在磁盘的已用与总量。 */
async function refreshStorageDisk() {
    try {
        var res = await fetch('/api/storage/disk', {cache: 'no-store', headers: authHeaders()});
        if (res.status === 401) {
            openLogin();  // 未认证:弹出登录卡片,与进度页一致。
            return;
        }
        renderStorageDisk(await res.json());
    } catch (e) {
        // 拉取失败时保留上次显示,交由进度页的断线提示统一反馈。
    }
}

function renderStorageDisk(data) {
    var path = document.getElementById('storageDiskPath');
    var fill = document.getElementById('storageDiskFill');
    var value = document.getElementById('storageDiskValue');
    var cachePath = document.getElementById('storageCachePath');
    var cacheValue = document.getElementById('storageCacheValue');
    data = data || {};
    path.textContent = data.directory || '—';
    path.title = path.textContent;  // 长路径靠悬停提示查看全文。
    if (data.total) {
        fill.style.width = data.percent + '%';
        value.textContent = data.used_text + ' / ' + data.total_text;
    } else {
        fill.style.width = '0%';  // 磁盘读取失败退回空态,不影响缓存行显示。
        value.textContent = '—';
    }
    cachePath.textContent = data.cache_directory || '—';
    cachePath.title = cachePath.textContent;
    cacheValue.textContent = data.cache_text || '—';
}

var storageTimer = 0;  // 记录页的轮询定时器,只在记录页可见时查询,避免无谓的数据库访问。

function startStoragePolling() {
    if (!storageTimer) {
        storageTimer = setInterval(function () {
            if (currentSection === 'storage') {
                refreshStorage();
            }
        }, STORAGE_POLL_INTERVAL_MS);
    }
}

/* 与页面同风格的确认弹窗(替代原生 confirm),返回 Promise<boolean>。 */
var confirmResolve = null;

function askConfirm(text, title) {
    return new Promise(function (resolve) {
        document.getElementById('confirmTitle').textContent = title || '确认操作';
        document.getElementById('confirmText').textContent = text || '';
        confirmResolve = resolve;
        document.getElementById('confirmModal').hidden = false;
    });
}

function closeConfirm(result) {
    document.getElementById('confirmModal').hidden = true;
    if (confirmResolve) {
        var resolve = confirmResolve;
        confirmResolve = null;  // 先清空再回调,避免回调内再次触发时串台。
        resolve(result);
    }
}

/* 复用确认弹窗展示提示信息:只保留"确定"按钮(替代原生 alert)。 */
function askAlert(text, title) {
    var card = document.querySelector('#confirmModal .modal-card');
    var ok = document.getElementById('confirmOk');
    var cancel = document.getElementById('confirmCancel');
    card.classList.add('alert-card');  // 收窄到与登录卡片一致的比例。
    ok.classList.remove('danger');  // 提示框不是危险操作,确定按钮不用红色悬停。
    cancel.hidden = true;  // 提示框无需取消按钮。
    return askConfirm(text, title).then(function (result) {
        card.classList.remove('alert-card');
        ok.classList.add('danger');  // 恢复,不影响后续"移除监听"的确认框。
        cancel.hidden = false;
        return result;
    });
}

// ESC 关闭确认/提示弹窗,等同取消。
function confirmEscape(event) {
    if (event.key !== 'Escape') {
        return;
    }
    if (document.getElementById('confirmModal').hidden) {
        return;  // 未打开时不处理,避免影响其它弹窗。
    }
    closeConfirm(false);
    /* 阻止同一节点(document)上后续监听(如 settingsEscape)继续处理这次 ESC:
       本函数关掉提示弹窗后,后续监听再查 confirmModal.hidden 已是 true,
       会误判为"没有提示弹窗"而连带关闭下层的修改配置弹窗。 */
    event.stopImmediatePropagation();
}

function bindConfirm() {
    document.getElementById('confirmOk').onclick = function () {
        closeConfirm(true);
    };
    document.getElementById('confirmCancel').onclick = function () {
        closeConfirm(false);
    };
    document.getElementById('confirmClose').onclick = function () {
        closeConfirm(false);
    };
    document.getElementById('confirmModal').onclick = function (event) {
        if (event.target === this) {
            closeConfirm(false);  // 点击遮罩空白处等同取消。
        }
    };
    document.addEventListener('keydown', confirmEscape);
}

/* 登录卡片:替代浏览器原生的 Basic 认证弹窗,沿用页面毛玻璃风格。 */

/* 未勾选"30天内免登录"时,令牌只存放在 sessionStorage:
   关闭标签页即被清空,下次必须重新登录。
   Cookie 无法做到"关闭标签页即失效"(会话Cookie要整个浏览器退出才清),
   所以未勾选时服务端不下发Cookie,改由前端持令牌随请求带来。 */
function setSessionToken(token) {
    try {
        if (token) {
            sessionStorage.setItem('trmd_token', token);
        } else {
            sessionStorage.removeItem('trmd_token');
        }
    } catch (e) {
        // 隐私模式等 sessionStorage 不可用的场景直接忽略。
    }
}

function authHeaders() {
    var token = '';
    try {
        token = sessionStorage.getItem('trmd_token') || '';
    } catch (e) {
        token = '';
    }
    return token ? {Authorization: 'Bearer ' + token} : {};
}

/* 退出登录:通知服务端轮换令牌并清除Cookie,然后回到登录卡片。 */
async function logout() {
    var dropdown = document.getElementById('menuDropdown');
    if (dropdown) {
        dropdown.hidden = true;  // 先收起菜单,避免与询问框叠加。
    }
    var ok = await askConfirm('退出后需要重新输入账号密码。', '退出登录');
    if (!ok) {
        return;
    }
    try {
        await fetch('/api/logout', {
            method: 'POST',
            headers: Object.assign({'Content-Type': 'application/json'}, authHeaders())
        });
    } catch (e) {
        // 请求失败也要在本地清理,避免界面停留在已登录状态。
    }
    setSessionToken('');  // 清掉未勾选免登录时的临时令牌。
    openLogin();  // 重新弹出登录卡片并隐藏页面内容。
}

function initLogout() {
    if (document.body.getAttribute('data-auth') !== '1') {
        return;  // 未设置密码时无需退出登录入口。
    }
    var btn = document.getElementById('btnLogout');
    if (!btn) {
        return;
    }
    btn.hidden = false;
    btn.onclick = logout;
}

var loginShown = false;

function openLogin() {
    if (loginShown) {
        return;  // 每秒轮询都会触发,已展示时不再重复打开。
    }
    loginShown = true;
    document.getElementById('loginPass').value = '';
    document.getElementById('loginModal').hidden = false;
    document.body.classList.add('logged-out');  // 未登录时隐藏页面卡片,只留渐变背景。
    var user = document.getElementById('loginUser');
    if (user.value) {
        document.getElementById('loginPass').focus();
    } else {
        user.focus();
    }
}

function closeLogin() {
    loginShown = false;
    document.getElementById('loginModal').hidden = true;
    document.body.classList.remove('logged-out');  // 恢复页面内容。
}

async function submitLogin() {
    var remember = document.getElementById('loginRemember').checked;
    try {
        var res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: document.getElementById('loginUser').value,
                password: document.getElementById('loginPass').value,
                remember: document.getElementById('loginRemember').checked
            })
        });
        var data = await res.json();
        if (!data.status) {
            await askAlert('账号或密码不正确，请重新输入。', '登录失败');
            return;
        }
        // 勾选"30天内免登录"时服务端已下发Cookie;未勾选则把令牌留在本标签页。
        setSessionToken(remember ? '' : (data.token || ''));
        // 清空指纹,确保登录后必定重绘一次并重建列表(否则数据未变会被跳过)。
        lastRenderKey = '';
        lastStructKey = null;
        lastUploadStructKey = null;
        closeLogin();
        if (data.first_login) {
            openSupport();  // 保持原先"首次登录展示支持作者卡片"的行为。
        }
        refresh();
    } catch (e) {
        await askAlert('无法连接程序,请稍后重试。', '登录失败');
    }
}

function bindLogin() {
    document.getElementById('loginSubmit').onclick = submitLogin;
    var user = document.getElementById('loginUser');
    var pass = document.getElementById('loginPass');
    user.onkeydown = function (event) {
        if (event.key === 'Enter') {
            pass.focus();
        }
    };
    pass.onkeydown = function (event) {
        if (event.key === 'Enter') {
            submitLogin();
        }
    };
    // 每输入一个字符就推进一格渐变,复用官方"发送消息时推进"的同一套逻辑。
    var advance = function () {
        if (!bgCtx) {
            return;  // 渐变背景未初始化成功时跳过。
        }
        bgAdvancePosition();
    };
    user.addEventListener('input', advance);
    pass.addEventListener('input', advance);
}

var removingListener = {};  // 正在等待确认或移除中的监听,避免重复点击被处理多次。

async function removeListener(kind, link) {
    if (!link || removingListener[link]) {
        return;  // 同一监听已在确认或处理中,忽略重复点击。
    }
    removingListener[link] = true;
    var ok = await askConfirm('确定移除该监听?\n' + link, '移除监听');
    if (!ok) {
        delete removingListener[link];
        return;
    }
    try {
        var res = await fetch('/api/listener/remove', {
            method: 'POST',
            headers: Object.assign({'Content-Type': 'application/json'}, authHeaders()),
            body: JSON.stringify({kind: kind, link: link})
        });
        var data = await res.json();
        if (!data.status) {
            window.alert('移除失败:' + (data.e_code || '未知错误。'));
        }
    } catch (e) {
        window.alert('移除失败:无法连接程序。');
    }
    delete removingListener[link];
    refresh();  // 移除后立即刷新,无需等待下一次轮询。
}

async function setPause(paused) {
    try {
        var res = await fetch('/api/pause', {
            method: 'POST',
            headers: Object.assign({'Content-Type': 'application/json'}, authHeaders()),
            body: JSON.stringify({paused: paused})
        });
        var data = await res.json();
        if (!data.status) {
            window.alert('操作失败:' + (data.e_code || '未知错误。'));
        }
    } catch (e) {
        window.alert('操作失败:无法连接程序。');
    }
    // 乐观更新:服务端通过事件循环异步切换标志,立即刷新拿到的快照可能仍是旧值,
    // 会导致按钮文字与 lastPaused 滞后约一个轮询周期、期间无法反向切换。
    // 因此以本次请求的目标状态为准直接更新,无需等待轮询回流。
    lastPaused = paused;
    renderPauseState(paused);
    refresh();  // 切换后刷新快照,与后端状态对齐。
}

function renderPauseState(isPaused) {
    var btn = document.getElementById('btnPause');
    if (!btn) {
        return;  // 页面未包含暂停按钮时跳过。
    }
    // 图标用 U+FE0F 以 emoji 彩色字形呈现(⏸️ / ▶️),两种 emoji 字形高度一致,
    // 不会造成顶栏高度抖动、下方卡片下移。
    btn.textContent = isPaused ? '▶\uFE0F恢复' : '⏸\uFE0F暂停';
    btn.classList.toggle('paused', !!isPaused);
}

function uploadDone(file) {
    return file.state === 'success' || file.state === 'sent';
}

// 无筛选时用于把活跃任务置顶的排序权重:进行中(downloading/uploading) > 队列中(pending) > 已完成/已跳过(success/sent/skip) > 失败(failure)。
// 排序在数组副本上进行,不改动后端快照数据,且为稳定排序,同权重的任务保持原有顺序。
function stateRank(state) {
    if (state === 'downloading' || state === 'uploading') {
        return 0;
    }
    if (state === 'pending') {
        return 1;
    }
    if (state === 'success' || state === 'sent' || state === 'skip') {
        return 2;
    }
    return 3;  // failure 等失败状态置底。
}

function getUploadGroups(tasks) {
    var groups = [];  // 按频道分组上传任务,保持频道首次出现的顺序。
    var index = {};
    var i;
    for (i = 0; i < tasks.length; i++) {
        var channel = tasks[i].channel || UNGROUPED_NAME;
        if (index[channel] === undefined) {
            index[channel] = groups.length;
            groups.push({channel: channel, name: tasks[i].chat || channel, files: []});
        }
        groups[index[channel]].files.push(tasks[i]);
    }
    for (i = 0; i < groups.length; i++) {
        var group = groups[i];
        group.count = group.files.length;
        group.complete = 0;
        group.failed = 0;
        group.total_byte = 0;
        group.done_byte = 0;
        for (var j = 0; j < group.files.length; j++) {
            var file = group.files[j];
            if (file.state === 'failure') {
                group.failed += 1;
                continue;  // 失败文件不计入分组进度基数,避免拖低进度。
            }
            var size = Number(file.size_byte) || 0;
            group.total_byte += size;
            if (uploadDone(file)) {
                group.complete += 1;
                group.done_byte += size;
            } else {
                group.done_byte += Math.min(Number(file.completed) || 0, size);  // 上传中的文件按已传字节计入。
            }
        }
        group.percent = group.total_byte ?
            Math.round(group.done_byte / group.total_byte * 1000) / 10 : 0;
        group.stat = groupStat(group.files, {});
    }
    return groups;
}

function uploadSummary(tasks) {
    var total = 0;  // 总量只统计未失败的上传文件,失败文件退出进度基数。
    var done = 0;
    var speed = 0;
    for (var i = 0; i < tasks.length; i++) {
        var file = tasks[i];
        if (file.state === 'failure') {
            continue;  // 失败文件不再计入总量与速度,避免进度被拉低。
        }
        var size = Number(file.size_byte) || 0;
        total += size;
        if (uploadDone(file)) {
            done += size;
        } else if (file.state === 'uploading') {
            done += Math.min(Number(file.completed) || 0, size);  // 上传中的文件按已传字节计入。
        }
        speed += Number(file.speed_value) || 0;
    }
    var remaining = speed && total > done ? (total - done) / speed : null;
    return {
        percent: total ? Math.round(done / total * 1000) / 10 : 0,
        info: sizeText(done) + '/' + sizeText(total),
        speed: speed ? sizeText(speed) + '/s' : '',
        remaining: remaining === null ? '' : secondsText(remaining)
    };
}

function uploadCount(tasks) {
    var count = {success: 0, failure: 0, uploading: 0, pending: 0, active: 0};
    for (var i = 0; i < tasks.length; i++) {
        var state = tasks[i].state;
        if (state === 'failure') {
            count.failure += 1;
        } else if (uploadDone(tasks[i])) {
            count.success += 1;
        } else {
            count.active += 1;
            if (state === 'uploading') {
                count.uploading += 1;
            } else {
                count.pending += 1;
            }
        }
    }
    return count;
}

function uploadRow(file) {
    var state = file.state || 'pending';
    var text = UPLOAD_TEXT[state] || '队列中';
    var cls = UPLOAD_CLASS[state] || 'status-pending';
    var progress;
    if (uploadDone(file)) {
        progress = progressCell(100);
    } else if (state === 'uploading') {
        progress = progressCell(file.percent || 0);
    } else {
        progress = '<span class="cell-progress"><span class="pct' +
            (state === 'pending' ? ' pending' : '') + '">' + text + '</span></span>';
    }
    // data-upload-id 供"上传列表结构未变时就地更新进度",避免每秒整表重建。
    return '<div class="task-row member-row" data-upload-id="' +
        escAttr(file.task_id || file.path || file.file) + '">' +
        '<span class="cell-name"><span class="ficon">' + (UPLOAD_ICON[state] || '⏳') + '</span>' +
        '<span class="fname" title="' + escAttr(file.path || file.file) + '">' + esc(file.path || file.file) + '</span></span>' +
        progress +
        '<span class="cell-size">' + dash(file.size) + '</span>' +
        '<span class="cell-speed">' + dash(file.speed) + '</span>' +
        '<span class="cell-remain">' + dash(file.remaining) + '</span>' +
        '<span class="cell-status ' + cls + '" title="' + escAttr(file.error) + '">' + text + '</span>' +
        '</div>';
}

function uploadStatusCell(group) {
    if (group.failed) {
        return '<span class="cell-status status-failed">失败 ' + group.failed + ' 个</span>';
    }
    if (group.complete === group.count) {
        return '<span class="cell-status status-done">已完成</span>';
    }
    return '<span class="cell-status status-running">上传中</span>';
}

function uploadBlock(group) {
    var key = 'upload:' + group.channel;
    var filtering = Boolean(statFilter.upload);
    var files = group.files;
    if (filtering) {
        files = files.filter(function (file) {
            return matchUploadState(file, statFilter.upload);
        });
        if (files.length === 0) {
            return '';  // 筛选后无匹配文件,不再显示该分组。
        }
    } else {
        // 无筛选卡片时按状态置顶:进行中 > 队列中 > 已完成/已跳过 > 失败,使活跃任务集中显示在最上方。
        files = files.slice().sort(function (a, b) {
            return stateRank(a.state) - stateRank(b.state);
        });
    }
    // 筛选时强制展开,否则结果会被折叠状态藏起来。
    var isCollapsed = filtering ? false : (collapsed[key] === undefined ? lastUploadCollapsed : collapsed[key]);
    var html = '<div class="group' + (isCollapsed ? '' : ' open') + '" data-channel="' + escAttr(key) + '" data-level="1">' +
        '<div class="group-head" data-channel="' + escAttr(key) + '">' +
        '<span class="cell-name"><span class="arrow"></span>' +
        '<span class="ficon">📺</span>' +
        '<span class="gname" title="' + escAttr(group.name) + '">' + esc(group.name) + '</span>' +
        '<span class="gcount">' + group.count + ' 个文件</span></span>' +
        progressCell(group.percent) +
        '<span class="cell-size">' + group.complete + '/' + group.count + '</span>' +
        groupStatCells(group.stat) +
        uploadStatusCell(group) +
        '</div>' +
        '<div class="group-body"' + (isCollapsed ? ' style="display:none"' : '') + '>';
    for (var i = 0; i < files.length; i++) {
        html += uploadRow(files[i]);
    }
    return html + '</div></div>';
}

function uploadList(tasks) {
    if (tasks.length === 0) {
        return '<div class="empty">暂无上传任务。</div>';
    }
    var html = '';
    var groups = getUploadGroups(tasks);  // 频道 > 文件完整路径,一级可折叠。
    for (var i = 0; i < groups.length; i++) {
        html += uploadBlock(groups[i]);
    }
    if (statFilter.upload && !html) {
        return '<div class="empty">' + (UPLOAD_EMPTY_TEXT[statFilter.upload] || '没有符合条件的文件。') + '</div>';
    }
    return html;
}

function syncUploadHeads() {
    var list = document.getElementById('upload');
    if (!list || !list.parentNode) {
        return;
    }
    var head = list.parentNode.querySelector('.list-head');
    var level = 1;
    var nodes = list.querySelectorAll('.group.open');
    for (var i = 0; i < nodes.length; i++) {
        if (groupVisible(nodes[i])) {
            level = 2;  // 有任意频道展开时,最内层即为文件行。
            break;
        }
    }
    head.querySelector('.h-name .htext').textContent = UPLOAD_HEAD_NAME[level - 1];
    head.querySelector('.h-size .htext').textContent = UPLOAD_HEAD_SIZE[level - 1];
}

function renderUpload(uploads) {
    var count = uploadCount(uploads);
    document.getElementById('badgeUpload').textContent = count.active;
    /* 只有结构变化(文件增减/状态改变)才重建 DOM,否则仅就地更新进度,避免每秒整表重建。 */
    var uploadKey = uploadStructKey(uploads);
    if (uploadKey !== lastUploadStructKey) {
        lastUploadStructKey = uploadKey;
        /* 空态以"是否存在上传文件(含已完成的)"判断,而非"是否有活跃任务"。
           否则全部上传结束后 count.active 为 0,已完成的文件会被空态整块隐藏,
           需新建任务才重新出现。 */
        // 处于筛选状态时,无匹配项应提示具体的筛选条件,而非笼统的"暂无上传任务。"。
        var uploadEmpty = '暂无上传任务。';
        if (statFilter.upload) {
            uploadEmpty = UPLOAD_EMPTY_TEXT[statFilter.upload] || uploadEmpty;
        }
        document.getElementById('upload').innerHTML = uploads.length > 0 ? uploadList(uploads) : '<div class="empty">' + uploadEmpty + '</div>';
        syncToggleUpload();
        syncUploadHeads();
        bindGroups();  // 上传列表渲染完成后统一绑定折叠事件。
    } else {
        updateUploadRows(uploads);
    }
    renderOverall(uploadSummary(uploads), count.active, SUMMARY_IDS.upload);
    lastUploadFinished = count.success + count.failure;
    renderStat('uploadStat', [
        statCell('成功', count.success, 'ok', 'success', 'upload'),
        statCell('失败', count.failure, 'bad', 'failure', 'upload'),
        statCell('上传中', count.uploading, '', 'uploading', 'upload'),
        statCell('队列', count.pending, 'skip', 'pending', 'upload')
    ]);
    return count.active;
}

var lastRenderKey = '';  // 上次渲染的数据指纹,用于跳过无变化的重绘。
var lastStructKey = null;  // 列表结构指纹,结构不变则不重建列表 DOM。(初始为 null 而非 '',否则空链接时 structKeyOf 返回 '' 会被误判为"未变化",导致首次渲染跳过 renderList、列表区只剩表头)
var lastUploadStructKey = null;  // 上传列表结构指纹,同上。

/* 轮询间隔(毫秒)。默认 1 秒。
   若设备压力明显,调大到 2000~3000 可直接砍掉一半以上的拉取与渲染开销,
   代价只是数字更新变慢。 */
var POLL_INTERVAL_MS = 1000;

/* 上传列表结构指纹:文件路径 + 状态,不含进度/速度等每秒变化的数值。 */
function uploadStructKey(uploads) {
    var parts = [];
    for (var i = 0; i < (uploads || []).length; i++) {
        parts.push((uploads[i].path || uploads[i].file || '') + '|' + uploads[i].state);
    }
    return parts.join(';');
}

/* 上传列表结构未变时,只就地更新各行的进度与速度文字,不重建 DOM。 */
function updateUploadRows(uploads) {
    var live = {};
    var i;
    for (i = 0; i < (uploads || []).length; i++) {
        live[String(uploads[i].task_id || uploads[i].path || uploads[i].file)] = uploads[i];
    }
    var rows = document.querySelectorAll('#upload [data-upload-id]');
    for (i = 0; i < rows.length; i++) {
        var row = rows[i];
        var file = live[row.getAttribute('data-upload-id')];
        if (!file) {
            continue;
        }
        var percent = uploadDone(file) ? 100 : (Number(file.percent) || 0);
        var fill = row.querySelector('.fill');
        if (fill) {
            fill.style.width = percent + '%';  // 桌面端横向条。
            var cell = fill.closest('.cell-progress');  // 手机端圆环依赖 --p,需同步更新。
            if (cell) {
                cell.style.setProperty('--p', percent + '%');
            }
        }
        var pct = row.querySelector('.pct');
        if (pct && fill) {
            pct.textContent = percent + '%';
        }
        var speed = row.querySelector('.cell-speed');
        if (speed) {
            speed.textContent = dash(file.speed);
        }
        var remain = row.querySelector('.cell-remain');
        if (remain) {
            remain.textContent = dash(file.remaining);
        }
    }
}

/* 列表结构指纹:频道、链接、成员名称与状态。
   刻意不包含进度/速度等每秒变化的数值,否则每次轮询都会触发重建。 */
function structKeyOf(data) {
    var parts = [];
    var links = data.links || [];
    for (var i = 0; i < links.length; i++) {
        var members = links[i].queue || [];
        var sig = [];
        for (var j = 0; j < members.length; j++) {
            sig.push(members[j].name + '|' + members[j].state);
        }
        parts.push(links[i].link + '#' + sig.join(','));
    }
    return parts.join(';');
}

/* 结构未变化时,只就地更新"正在下载"的行:
   改宽度与文字,避免整表 DOM 重建(仅这几行重排)。 */
function updateTaskRows(data) {
    var tasks = data.tasks || [];
    var live = {};
    var i;
    for (i = 0; i < tasks.length; i++) {
        live[String(tasks[i].id)] = tasks[i];
    }
    var rows = document.querySelectorAll('#download [data-task-id]');
    for (i = 0; i < rows.length; i++) {
        var row = rows[i];
        var task = live[row.getAttribute('data-task-id')];
        if (!task) {
            continue;  // 该任务已结束,等结构变化时整行替换。
        }
        var fill = row.querySelector('.fill');
        if (fill) {
            var pct = task.percent + '%';
            fill.style.width = pct;  // 桌面端横向条。
            var cell = fill.closest('.cell-progress');  // 手机端圆环依赖 --p,需同步更新。
            if (cell) {
                cell.style.setProperty('--p', pct);
            }
        }
        var pct = row.querySelector('.pct');
        if (pct) {
            pct.textContent = task.percent + '%';
        }
        var size = row.querySelector('.cell-size');
        if (size) {
            size.textContent = dash(task.info);
        }
        var speed = row.querySelector('.cell-speed');
        if (speed) {
            speed.textContent = dash(task.speed);
        }
        var remain = row.querySelector('.cell-remain');
        if (remain) {
            remain.textContent = dash(task.remaining);
        }
    }
}

function render(data, force) {
    /* 数据未变化时直接跳过整页重绘。
       原本每秒都会重建整个列表 DOM,导致所有毛玻璃图层失效并重新采样背景,
       这是 GPU 占用的主要来源。空闲(无任务变化)时可完全省掉这部分开销。 */
    var key = JSON.stringify(data);
    if (!force && key === lastRenderKey) {
        return;
    }
    lastRenderKey = key;
    var downloads = (data.tasks || []).length;
    lastDownloadActive = downloads;
    document.getElementById('badgeDownload').textContent = downloads;
    renderOverall(data.summary, downloads, SUMMARY_IDS.download);
    renderStat('stat', [
        statCell('成功', data.count.success, 'ok', 'success', 'download'),
        statCell('失败', data.count.failure, 'bad', 'failure', 'download'),
        statCell('跳过', data.count.skip, 'skip', 'skip', 'download'),
        statCell('下载中', downloads, '', 'active', 'download'),
        statCell('队列', countQueueMembers(data.links), 'queue', 'queue', 'download')
    ]);
    lastUploadActive = renderUpload(data.uploads || []);
    lastListenCount = renderListeners(data.listeners);
    lastPaused = !!data.is_paused;
    renderPauseState(lastPaused);
    renderOuterLinks(data.outer_links);
    renderStatus();
    // 只有列表结构变化(成员增减/状态改变)才重建 DOM;
    // 否则仅就地更新正在下载的行,避免每秒整表重建带来的重排与重绘。
    var structKey = structKeyOf(data);
    if (structKey !== lastStructKey) {
        lastStructKey = structKey;
        renderList(data);
    } else {
        updateTaskRows(data);
    }
    syncBackgroundProgress(data.count.success + data.count.failure + data.count.skip + lastUploadFinished);
}

function syncBackgroundProgress(finished) {  // 下载或上传每完成一个任务,背景渐变就推进一格,与官方发送消息时推进一致。
    if (bgLastProgress < 0) {
        bgLastProgress = finished;  // 首次只记录基数,不触发移动。
        return;
    }
    if (finished > bgLastProgress) {
        bgLastProgress = finished;
        bgAdvancePosition();
    }
    if (finished < bgLastProgress) {
        bgLastProgress = finished;  // 任务被清空或重置时同步基数,避免数字回退后误触发。
    }
}

async function refresh(force) {
    try {
        var res = await fetch('/api/progress', {cache: 'no-store', headers: authHeaders()});
        if (res.status === 401) {
            openLogin();  // 未认证:前端展示登录卡片,不再触发浏览器原生弹窗。
            return;
        }
        document.body.classList.remove('logged-out');  // 认证通过,显示页面内容。
        var json = await res.json();
        lastSnapshot = json;  // 缓存最新快照,供设置弹窗回填保存目录。
        render(json, force);
        refreshNameTip();  // 列表重绘后按当前鼠标位置重新定位提示。
        document.getElementById('offline').style.display = 'none';
    } catch (e) {
        document.getElementById('offline').style.display = 'block';
    }
}

function bindSections() {
    var items = document.querySelectorAll('.side-item');
    for (var i = 0; i < items.length; i++) {
        items[i].onclick = function () {
            switchSection(this.getAttribute('data-section'));
        };
    }
}

function bindPause() {
    var btn = document.getElementById('btnPause');
    if (!btn) {
        return;  // 页面未包含暂停按钮时跳过绑定。
    }
    btn.onclick = function () {
        setPause(!lastPaused);  // 以当前展示状态为准,再次点击即切换暂停/恢复。
    };
}

function bindListenTabs() {
    var tabs = document.querySelectorAll('#listenTabs .tab');
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].onclick = function () {
            switchListen(this.getAttribute('data-listen'));
        };
    }
}

function bindListenRemove() {
    var box = document.getElementById('page-listener');  // 用事件委托,避免每次轮询重新绑定。
    box.onclick = function (event) {
        var target = event.target;
        if (!target || !target.classList || !target.classList.contains('btn-del')) {
            return;
        }
        removeListener(target.getAttribute('data-kind'), target.getAttribute('data-link'));
    };
}

function openSupport() {
    document.getElementById('supportModal').hidden = false;
}

function closeSupport() {
    document.getElementById('supportModal').hidden = true;
}

function supportEscape(event) {
    if (event.key === 'Escape' && !document.getElementById('supportModal').hidden) {
        closeSupport();
    }
}

function initSettings() {
    var btn = document.getElementById('btnSettings');
    if (btn) {
        btn.onclick = openSettings;
    }
    var close = document.getElementById('settingsClose');
    if (close) {
        close.onclick = closeSettings;
    }
    var cancel = document.getElementById('saveDirCancel');
    if (cancel) {
        cancel.onclick = closeSettings;
    }
    var apply = document.getElementById('saveDirApply');
    if (apply) {
        apply.onclick = applyConfig;
    }
    document.addEventListener('keydown', settingsEscape);  // ESC 关闭弹窗(不再响应遮罩点击关闭)。
    // 修改配置时每输入一个字符也推进背景涂鸦渐变,与登录框一致(复用官方推进逻辑)。
    var cfgAdvance = function () {
        if (!bgCtx) {
            return;  // 渐变背景未初始化成功时跳过。
        }
        bgAdvancePosition();
    };
    ['saveDirInput', 'maxDownload', 'maxUpload', 'maxRetryDownload', 'maxRetryUpload'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', cfgAdvance);
        }
    });
}

var settingsOriginal = null;  // 打开配置弹窗时的原值快照:用于"只提交改动项",避免全量保存。

function openSettings() {
    setMenuOpen(false);  // 先收起顶部菜单,避免与设置弹窗叠加。
    var modal = document.getElementById('settingsModal');
    if (lastSnapshot) {
        if (lastSnapshot.save_directory) {
            document.getElementById('saveDirInput').value = lastSnapshot.save_directory;
        }
        setNum('maxDownload', lastSnapshot.max_tasks && lastSnapshot.max_tasks.download);
        setNum('maxUpload', lastSnapshot.max_tasks && lastSnapshot.max_tasks.upload);
        setNum('maxRetryDownload', lastSnapshot.max_retries && lastSnapshot.max_retries.download);
        setNum('maxRetryUpload', lastSnapshot.max_retries && lastSnapshot.max_retries.upload);
    }
    /* 未配置机器人(HAS_BOT)时,上传并发/重试的修改不会生效,隐藏这两项避免用户改了无效果。 */
    var uploadAvailable = HAS_BOT;
    ['maxUpload', 'maxRetryUpload'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el && el.parentElement) {
            el.parentElement.style.display = uploadAvailable ? '' : 'none';
        }
    });
    /* 记录"打开弹窗时输入框里的值"作为改动比对基准(只读 lastSnapshot 会被轮询刷新而失准)。 */
    settingsOriginal = {
        save_directory: (document.getElementById('saveDirInput').value || '').trim(),
        max_tasks: {download: numVal('maxDownload'), upload: numVal('maxUpload')},
        max_retries: {download: numVal('maxRetryDownload'), upload: numVal('maxRetryUpload')}
    };
    modal.hidden = false;
}

function closeSettings() {
    document.getElementById('settingsModal').hidden = true;
}

function settingsEscape(event) {
    if (event.key !== 'Escape') {
        return;
    }
    // 有上层提示/确认弹窗时,ESC 已由 confirmEscape 处理(它 stopImmediatePropagation,正常情况下到不了这);
    // 此处若仍检测到它开着,则仅退出,绝不连带关闭修改配置弹窗。
    if (!document.getElementById('confirmModal').hidden) {
        return;
    }
    if (!document.getElementById('settingsModal').hidden) {
        closeSettings();
    }
}

/* 冲突检测:lastSnapshot由后台每秒轮询刷新,settingsOriginal是打开弹窗时的基准。
   本次要提交的项若在别处被改过,提交会覆盖对方的改动,因此返回冲突项列表供调用处确认;
   本次不提交的项即使被改过也不会被覆盖,所以只检查真正要改的那些项。
   抽成独立函数是为了在第一次提交前与二次确认后的第二次提交前各调用一次,避免确认框
   停留期间后台被别处改动,却直接用旧值覆盖对方的改动。 */
function checkConfigConflict(dirChanged, tasksChanged, retriesChanged, lastSnapshot, settingsOriginal) {
    var conflictParts = [];
    if (dirChanged && lastSnapshot && settingsOriginal
        && (lastSnapshot.save_directory || '') !== settingsOriginal.save_directory) {
        conflictParts.push('保存目录');
    }
    if (tasksChanged && lastSnapshot && lastSnapshot.max_tasks && settingsOriginal
        && (lastSnapshot.max_tasks.download !== settingsOriginal.max_tasks.download
            || lastSnapshot.max_tasks.upload !== settingsOriginal.max_tasks.upload)) {
        conflictParts.push('并发数');
    }
    if (retriesChanged && lastSnapshot && lastSnapshot.max_retries && settingsOriginal
        && (lastSnapshot.max_retries.download !== settingsOriginal.max_retries.download
            || lastSnapshot.max_retries.upload !== settingsOriginal.max_retries.upload)) {
        conflictParts.push('重试次数');
    }
    return conflictParts;
}

/* 冲突取消后把后台实时配置回填到弹窗,并刷新比对基准:否则弹窗仍显示旧值,用户不知别处已改,
   再次点应用又会撞到同一处冲突;回填后弹窗与后台一致,再点应用即为"未做任何修改"。 */
function syncSettingsFromSnapshot() {
    if (!lastSnapshot) {
        return;
    }
    var dirInput = document.getElementById('saveDirInput');
    if (dirInput && lastSnapshot.save_directory) {
        dirInput.value = lastSnapshot.save_directory;
    }
    if (lastSnapshot.max_tasks) {
        setNum('maxDownload', lastSnapshot.max_tasks.download);
        setNum('maxUpload', lastSnapshot.max_tasks.upload);
    }
    if (lastSnapshot.max_retries) {
        setNum('maxRetryDownload', lastSnapshot.max_retries.download);
        setNum('maxRetryUpload', lastSnapshot.max_retries.upload);
    }
    settingsOriginal = {
        save_directory: lastSnapshot.save_directory,
        max_tasks: lastSnapshot.max_tasks ? {
            download: lastSnapshot.max_tasks.download,
            upload: lastSnapshot.max_tasks.upload
        } : {download: null, upload: null},
        max_retries: lastSnapshot.max_retries ? {
            download: lastSnapshot.max_retries.download,
            upload: lastSnapshot.max_retries.upload
        } : {download: null, upload: null}
    };
}

async function applyConfig() {
    var dirInput = document.getElementById('saveDirInput');
    var path = (dirInput.value || '').trim();
    if (!path) {
        await askAlert('保存目录不能为空。', '修改配置');
        return;
    }
    var maxTasks = {download: numVal('maxDownload'), upload: numVal('maxUpload')};
    var maxRetries = {download: numVal('maxRetryDownload'), upload: numVal('maxRetryUpload')};
    /* 字段级校验:用户改了哪个就只提示哪个;多个都有问题时再一起提示。 */
    var _errParts = [];
    if (maxTasks.download === null || maxTasks.download < 1 || maxTasks.download > 10) {
        _errParts.push('下载并发数必须是1到10之间的整数');
    }
    if (maxTasks.upload === null || maxTasks.upload < 1 || maxTasks.upload > 10) {
        _errParts.push('上传并发数必须是1到10之间的整数');
    }
    if (maxRetries.download === null || maxRetries.download < 1) {
        _errParts.push('下载重试次数必须大于0');
    }
    if (maxRetries.upload === null || maxRetries.upload < 1) {
        _errParts.push('上传重试次数必须大于0');
    }
    if (_errParts.length) {
        await askAlert(_errParts.join('，') + '。', '修改配置');
        return;
    }
    /* 只提交真正改动的项:未改动的接口不再请求(后端就不会重复写配置),
       改一项也只落一次盘,杜绝"改一处却保存三次"的日志。 */
    var dirChanged = !settingsOriginal || settingsOriginal.save_directory !== path;
    var tasksChanged = !settingsOriginal
        || settingsOriginal.max_tasks.download !== maxTasks.download
        || settingsOriginal.max_tasks.upload !== maxTasks.upload;
    var retriesChanged = !settingsOriginal
        || settingsOriginal.max_retries.download !== maxRetries.download
        || settingsOriginal.max_retries.upload !== maxRetries.upload;
    if (!dirChanged && !tasksChanged && !retriesChanged) {
        await askAlert('未做任何修改。', '修改配置');
        return;
    }
    try {
        /* 提交前比对后台实时配置与打开弹窗时的基准:本次要提交的项若在别处被改过,
           提交会覆盖对方的改动,因此先让用户确认;二次确认后的第二次提交前还会再比对一次。 */
        var conflictParts = checkConfigConflict(dirChanged, tasksChanged, retriesChanged, lastSnapshot, settingsOriginal);
        if (conflictParts.length) {
            var goon = await askConfirm(
                conflictParts.join('、') + '已在别处被修改，应用将覆盖该改动，是否继续？', '修改配置');
            if (!goon) {
                syncSettingsFromSnapshot();
                return;
            }
        }
        /* 多项改动合并成一次请求:分开请求会让后端写多次配置文件,且其中一项失败时已经写入的
           项无法回退(部分生效)。合并后由后端统一校验、只落盘一次,要么全部生效要么一个都不改。
           三个配置路径在后端已等价,这里沿用save_directory路径作为统一入口。 */
        var payload = {};
        if (dirChanged) {
            payload.save_directory = path;
        }
        if (tasksChanged) {
            payload.max_tasks = maxTasks;
        }
        if (retriesChanged) {
            payload.max_retries = maxRetries;
        }
        var res = await fetch('/api/config/save_directory', {
            method: 'POST',
            headers: Object.assign({'Content-Type': 'application/json'}, authHeaders()),
            body: JSON.stringify(payload)
        });
        var data = await res.json();
        /* 保存目录不存在时后端不创建、不落盘,先回来请求二次确认:
           取消则什么都不改;确定则带confirm_directory重新提交,由后端创建目录再保存。 */
        if (data.need_confirm) {
            var ok = await askConfirm((data.e_code || '目录不存在，是否创建') + '。', '修改配置');
            if (!ok) {
                return;
            }
            /* 二次确认框停留期间后台可能被别处改动:重新比对一次,避免直接用旧值覆盖对方改动。 */
            conflictParts = checkConfigConflict(dirChanged, tasksChanged, retriesChanged, lastSnapshot, settingsOriginal);
            if (conflictParts.length) {
                var goon2 = await askConfirm(
                    conflictParts.join('、') + '已在别处被修改，应用将覆盖该改动，是否继续？', '修改配置');
                if (!goon2) {
                    syncSettingsFromSnapshot();
                    return;
                }
            }
            payload.confirm_directory = true;
            res = await fetch('/api/config/save_directory', {
                method: 'POST',
                headers: Object.assign({'Content-Type': 'application/json'}, authHeaders()),
                body: JSON.stringify(payload)
            });
            data = await res.json();
        }
        if (!data.status) {
            await askAlert((data.e_code || '配置更新失败') + '。', '修改配置');
            return;
        }
        if (dirChanged && lastSnapshot) {
            lastSnapshot.save_directory = path;
        }
        if (tasksChanged && lastSnapshot) {
            lastSnapshot.max_tasks = {download: maxTasks.download, upload: maxTasks.upload};
        }
        if (retriesChanged && lastSnapshot) {
            lastSnapshot.max_retries = {download: maxRetries.download, upload: maxRetries.upload};
        }
        /* 保存成功后刷新改动比对基准:否则窗口不关闭时再次点应用,仍会拿旧值比对出"有改动",
           导致重复提交、重复写盘(后台反复提示配置文件已保存)。 */
        settingsOriginal = {
            save_directory: path,
            max_tasks: {download: maxTasks.download, upload: maxTasks.upload},
            max_retries: {download: maxRetries.download, upload: maxRetries.upload}
        };
        await askAlert('配置已生效。', '修改配置');
    } catch (e) {
        await askAlert('请求失败：' + e + '。', '修改配置');
    }
}

function setNum(id, val) {
    var el = document.getElementById(id);
    if (el && val !== null && val !== undefined) {
        el.value = val;
    }
}

function numVal(id) {
    var raw = document.getElementById(id).value;
    if (raw === '' || raw === null) {
        return null;
    }
    var n = parseInt(raw, 10);
    return isNaN(n) ? null : n;
}

var OUTER_LINK_IDS = {github: 'linkGithub', subscribe_channel: 'linkChannel', video_tutorial: 'linkVideo'};

function renderOuterLinks(links) {
    Object.keys(OUTER_LINK_IDS).forEach(function (key) {
        var node = document.getElementById(OUTER_LINK_IDS[key]);
        var url = (links || {})[key];
        node.href = url || '#';
        node.hidden = !url;  // 后端未提供该链接时隐藏对应菜单项。
    });
}

function setMenuOpen(open) {
    document.getElementById('menuDropdown').hidden = !open;
}

function menuBtnClick(event) {
    event.stopPropagation();  // 阻止冒泡,避免立刻被外部点击处理关闭。
    setMenuOpen(document.getElementById('menuDropdown').hidden);
}

function menuOutsideClick(event) {
    if (!document.getElementById('menuWrap').contains(event.target)) {
        setMenuOpen(false);
    }
}

function menuEscape(event) {
    if (event.key === 'Escape') {
        setMenuOpen(false);
    }
}

function bindMenu() {
    document.getElementById('menuBtn').onclick = menuBtnClick;
    document.addEventListener('click', menuOutsideClick);
    document.addEventListener('keydown', menuEscape);
}

function isFirstLogin() {
    return document.body.getAttribute('data-first-login') === '1';  // 服务端在首次登录时写入该标记。
}

function bindSupport() {
    document.getElementById('supportBtn').onclick = openSupport;
    document.getElementById('supportClose').onclick = closeSupport;
    document.addEventListener('keydown', supportEscape);
    if (isFirstLogin()) {
        openSupport();
    }
}

var COLS_KEY = 'trmd_cols';  // 各表列宽的本地存储键。
var COLS_MIN = 48;  // 单列最小宽度,避免被拖到不可读。
var colsCache = {};  // 表名 -> 非弹性列的像素宽度数组。
var dragState = null;  // 拖拽过程中的临时状态。

function readDefaultCols(list) {
    var text = window.getComputedStyle(list).getPropertyValue('--cols');  // 自定义属性在隐藏元素上也可读取。
    /* 先去掉首列的 minmax(...):否则会把它里面的最小值(如 minmax(200px, 1fr) 的 200px)
       也当成固定列宽提取出来,导致列数凭空多一列、网格轨道与表头单元格数不匹配。
       缩放时反复重算还会让列数不断累加,最终表头错乱。 */
    text = text.replace(/minmax\([^)]*\)/g, '');
    var matches = text.match(/(\d+(?:\.\d+)?)px/g) || [];
    var widths = [];
    for (var i = 0; i < matches.length; i++) {
        widths.push(Math.round(parseFloat(matches[i])));
    }
    return widths.length ? widths : [COLS_MIN];
}

/* 弹性列在--cols中的位置:常规表在首位,记录表的频道列固定宽、弹性列在第2位。
   轨道按minmax(...)整体切分,避免其内部空格被当成分隔符。 */
function flexIndexOf(list) {
    var text = window.getComputedStyle(list).getPropertyValue('--cols') || '';
    var tracks = text.match(/minmax\([^)]*\)|\S+/g) || [];
    for (var i = 0; i < tracks.length; i++) {
        if (tracks[i].indexOf('minmax(') === 0) {
            return i;
        }
    }
    return 0;  // 未声明弹性列时按首位处理,与原有行为一致。
}

/* 固定列下标 -> 所在的网格列位置:弹性列之前原序,之后整体后移一位。 */
function fixedGridPos(index, flexIndex) {
    return index < flexIndex ? index : index + 1;
}

var measureEl = null;  // 复用同一个隐藏元素测量文字宽度,避免频繁创建节点。

function measureTextWidth(text, cs) {
    if (!measureEl) {
        measureEl = document.createElement('span');
        measureEl.style.cssText = 'position:absolute;left:-9999px;top:0;visibility:hidden;white-space:nowrap;';
        document.body.appendChild(measureEl);
    }
    measureEl.style.fontStyle = cs.fontStyle;
    measureEl.style.fontWeight = cs.fontWeight;
    measureEl.style.fontSize = cs.fontSize;
    measureEl.style.fontFamily = cs.fontFamily;
    measureEl.style.letterSpacing = cs.letterSpacing;
    measureEl.textContent = text;
    return measureEl.offsetWidth;
}

// 测量每列标题完整显示所需的宽度,作为该列不可被压缩的下限。
// 返回数组与表头列格一一对应,取用时按弹性列所在位置(flexIndexOf)取弹性列的下限。
function measureColMins(list) {
    var cells = list.querySelector('.list-head').children;
    var mins = [];
    for (var i = 0; i < cells.length; i++) {
        var cs = window.getComputedStyle(cells[i]);
        var need = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0) + 4;  // 内边距 + 余量,避免标题贴边。
        var text = cells[i].querySelector('.htext');
        if (text && text.textContent) {
            need += measureTextWidth(text.textContent, cs);
        }
        // 单元格可通过 --col-min 声明额外下限(如进度列需保证百分比可见)。
        var colMin = parseFloat(cs.getPropertyValue('--col-min')) || 0;
        mins.push(Math.max(COLS_MIN, Math.ceil(need), colMin));
    }
    return mins;
}

// 移动端弹性列(名称列)的最小宽度保底:
// 窄屏下固定列合计已超过视口,弹性列会退回到"标题文字宽度"(约百来像素),
// 再被嵌套缩进吃掉一部分后文件名几乎完全看不见。故移动端强制留出可读宽度,
// 超出的部分由横向滚动承载。
var FLEX_MIN_MOBILE = 200;

function flexColMin(measured) {
    var min = Math.max(COLS_MIN, measured || COLS_MIN);
    if (window.innerWidth <= 760) {
        min = Math.max(min, FLEX_MIN_MOBILE);
    }
    return min;
}

function applyCols(list, widths, flexMin, flexIndex) {
    if (flexIndex === undefined) {
        flexIndex = 0;  // 缺省按弹性列在首位,保持既有表格的行为。
    }
    var flex = 'minmax(' + (flexMin || COLS_MIN) + 'px, 1fr)';  // 弹性列不低于标题宽度,避免被其它列挤到看不见。
    var parts = [];
    for (var i = 0; i < widths.length; i++) {
        if (i === flexIndex) {
            parts.push(flex);
        }
        parts.push(widths[i] + 'px');
    }
    if (flexIndex >= widths.length) {
        parts.push(flex);  // 弹性列位于末列时补在末尾。
    }
    list.style.setProperty('--cols', parts.join(' '));
}

/* 分隔条的调整目标:返回{col:固定列下标, sign:拖动方向}。
   常规分隔条调整其右侧的固定列:向右拖动变窄,空间让给弹性列(sign=-1)。
   右侧是弹性列时弹性列没有宽度可调,改为调整左侧的固定列:向右拖动加宽,弹性列吸收差值(sign=1)。 */
function gripTarget(index, flexIndex) {
    var right = index + 1;  // 分隔条右侧的网格列。
    if (right === flexIndex) {
        return {col: index < flexIndex ? index : index - 1, sign: 1};
    }
    return {col: right < flexIndex ? right : right - 1, sign: -1};
}

function buildGrips(list) {
    var head = list.querySelector('.list-head');
    var cells = head.children;
    var table = list.getAttribute('data-table');
    var flexIndex = flexIndexOf(list);
    for (var i = 0; i < cells.length - 1; i++) {  // 末列格右侧为容器边界,不生成分隔条。
        if (cells[i].querySelector('.grip')) {
            continue;  // 已存在分隔条时不重复创建。
        }
        var target = gripTarget(i, flexIndex);
        var grip = document.createElement('span');
        grip.className = 'grip';
        grip.setAttribute('data-table', table);
        grip.setAttribute('data-index', target.col);
        grip.setAttribute('data-sign', target.sign);
        grip.onpointerdown = resizeStart;
        cells[i].appendChild(grip);
    }
}

function clampColsWidth(widths, index, value, maxFixed, mins, flexIndex) {
    var others = 0;
    for (var i = 0; i < widths.length; i++) {
        if (i !== index) {
            others += widths[i];
        }
    }
    // 下限取标题完整显示所需宽度,保证表头标题永不被压缩。
    var floor = Math.max(COLS_MIN, (mins && mins[fixedGridPos(index, flexIndex)]) || COLS_MIN);
    // 预留弹性列的最小宽度,避免固定列被拉到超出可用空间后挤压弹性列文字。
    var flexMin = flexColMin(mins && mins[flexIndex]);
    var max;
    if (window.innerWidth <= 760) {
        // 移动端允许横向滚动,不把列宽限制在视口内,用户可自由拖宽,超出部分滚动查看。
        max = Math.max(value, 900);
    } else {
        max = Math.max(COLS_MIN, maxFixed - others - flexMin);
    }
    // 标题优先:空间不足时保留标题所需宽度,宁可让行溢出也不压缩表头文字。
    return Math.max(floor, Math.min(value, max));
}

function resizeStart(event) {
    var grip = event.currentTarget;
    var list = grip.closest('.list');
    var head = list.querySelector('.list-head');
    var index = Number(grip.getAttribute('data-index'));
    var table = list.getAttribute('data-table');
    var widths = colsCache[table] || readDefaultCols(list);
    var style = window.getComputedStyle(head);
    var gap = parseFloat(style.columnGap) || 0;
    var padding = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
    dragState = {
        list: list,
        table: table,
        index: index,
        col: index,  // 每个分隔条都是其右侧固定列的左边界,统一调整该列,保证每列都有且仅有一个分隔条。
        sign: Number(grip.getAttribute('data-sign')) || -1,  // 向右拖动的方向,弹性列在右侧时由分隔条指定为反向。
        flexIndex: flexIndexOf(list),  // 弹性列所在位置,决定列宽与列下限的映射。
        origin: widths.slice(),
        widths: widths.slice(),
        startX: event.clientX,
        maxFixed: Math.max(head.clientWidth - padding - gap * widths.length, 0),
        mins: measureColMins(list)  // 各列标题所需的最小宽度,拖拽期间保持不变。
    };
    event.preventDefault();
    event.stopPropagation();
    document.body.classList.add('resizing');
    document.addEventListener('pointermove', resizeMove);
    document.addEventListener('pointerup', resizeEnd);
}

function resizeMove(event) {
    if (!dragState) {
        return;
    }
    var delta = event.clientX - dragState.startX;
    var value = dragState.origin[dragState.col] + delta * dragState.sign;
    dragState.widths[dragState.col] = clampColsWidth(dragState.widths, dragState.col, value, dragState.maxFixed, dragState.mins, dragState.flexIndex);
    applyCols(dragState.list, dragState.widths, flexColMin(dragState.mins[dragState.flexIndex]), dragState.flexIndex);
    event.preventDefault();
}

function resizeEnd() {
    if (!dragState) {
        return;
    }
    colsCache[dragState.table] = dragState.widths;
    try {
        localStorage.setItem(COLS_KEY, JSON.stringify(colsCache));  // 记住本次列宽,刷新后恢复。
    } catch (e) {
        // 隐私模式下写入失败可忽略。
    }
    document.body.classList.remove('resizing');
    document.removeEventListener('pointermove', resizeMove);
    document.removeEventListener('pointerup', resizeEnd);
    dragState = null;
}

function initCols() {
    try {
        colsCache = JSON.parse(localStorage.getItem(COLS_KEY) || '{}') || {};
    } catch (e) {
        colsCache = {};
    }
    var lists = document.querySelectorAll('.list[data-table]');
    for (var i = 0; i < lists.length; i++) {
        var list = lists[i];
        var table = list.getAttribute('data-table');
        var head = list.querySelector('.list-head');
        var flexIndex = flexIndexOf(list);  // 弹性列位置:常规表在首列,记录表在第2列。
        var widths = colsCache[table];
        if (!widths || widths.length !== head.children.length - 1) {
            widths = readDefaultCols(list);  // 列数变化或首次加载时回退到默认列宽。
        }
        var mins = measureColMins(list);
        var j;
        for (j = 0; j < widths.length; j++) {
            widths[j] = Math.max(widths[j], mins[fixedGridPos(j, flexIndex)]);  // 已保存的列宽也不得小于标题所需宽度。
        }
        colsCache[table] = widths;
        applyCols(list, widths, flexColMin(mins[flexIndex]), flexIndex);
        buildGrips(list);
    }
}

// 跨断点(旋转屏幕、缩放窗口)时重新应用列宽,
// 让移动端弹性列的保底最小宽度在进入/离开窄屏时正确生效或取消。
/* 缩放、窗口尺寸变化都会改变 innerWidth(CSS 像素),
   统一防抖重算列宽,避免高缩放比例下残留旧宽度导致表头错乱。 */
var resizeTimer = null;
window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(initCols, 150);
});

var savedSection = '';
var savedListen = '';
var savedStorage = '';
try {
    savedSection = localStorage.getItem(SECTION_KEY) || '';
    savedListen = localStorage.getItem(LISTEN_KEY) || '';
    savedStorage = localStorage.getItem(STORAGE_KEY) || '';
    collapsed = JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '{}') || {};  // 读回各分组折叠状态。
    allCollapsed = localStorage.getItem(ALL_KEY) === '1';
    uploadAllCollapsed = localStorage.getItem(UPLOAD_ALL_KEY) === '1';
    lastLinkCollapsed = localStorage.getItem(LINK_LAST_KEY) !== '0';  // 无记录时保持链接层默认折叠。
    lastUploadCollapsed = localStorage.getItem(UPLOAD_LAST_KEY) === '1';  // 无记录时保持上传频道层默认展开。
} catch (e) {
    savedSection = '';
    savedListen = '';
    savedStorage = '';
    collapsed = {};
    allCollapsed = false;
    uploadAllCollapsed = false;
    lastLinkCollapsed = true;
    lastUploadCollapsed = false;
}

function initVersion() {
    var tip = document.getElementById('logoVersion');
    var trmd = document.getElementById('tipTrmd');
    var pyrogram = document.getElementById('tipPyrogram');
    if (trmd.textContent.indexOf('__') === 0 || pyrogram.textContent.indexOf('__') === 0) {
        tip.hidden = true;  // 占位符未被服务端替换时隐藏,避免显示原始占位文本。
    }
}

/* 统一接管原生 title 提示:任何带 title 的元素都改用自定义玻璃提示,
   避免浏览器默认提示与自定义风格混杂(未截断的名称原本会冒出原生提示)。 */
var nameTipEl = null;
var nameTipFor = null;
var tipMouseX = 0;
var tipMouseY = 0;

function nameTipNode() {
    if (!nameTipEl) {
        nameTipEl = document.getElementById('nameTip');
    }
    return nameTipEl;
}

// 取最近的、带提示文案的元素(data-tip 或 title)。
function nameTipTarget(node) {
    if (!node || !node.closest) {
        return null;
    }
    return node.closest('[data-tip], [title]');
}

// 原生 title 会与自定义提示同时弹出,首次遇到时迁移为 data-tip 并移除 title。
function takeTipText(el) {
    if (el.hasAttribute('title')) {
        el.setAttribute('data-tip', el.getAttribute('title'));
        el.removeAttribute('title');
    }
    return el.getAttribute('data-tip') || '';
}

function showNameTip(el) {
    var text = takeTipText(el);
    var tip = nameTipNode();
    if (!text || !tip) {
        return;
    }
    tip.textContent = text;
    tip.classList.add('show');  // 先显示以取得实际尺寸,再据此定位。
    var rect = el.getBoundingClientRect();
    var left = rect.left;
    var top = rect.bottom + 8;
    var width = tip.offsetWidth;
    var height = tip.offsetHeight;
    if (left + width > window.innerWidth - 8) {
        left = Math.max(8, window.innerWidth - width - 8);
    }
    if (top + height > window.innerHeight - 8) {
        top = Math.max(8, rect.top - height - 8);  // 下方放不下时翻到上方。
    }
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
    nameTipFor = el;
}

function hideNameTip() {
    if (nameTipEl) {
        nameTipEl.classList.remove('show');
    }
    nameTipFor = null;
}

// 列表每秒重绘会销毁悬停元素,重绘后按当前鼠标位置重新定位提示。
function refreshNameTip() {
    if (!nameTipFor || nameTipFor.isConnected) {
        return;
    }
    var el = nameTipTarget(document.elementFromPoint(tipMouseX, tipMouseY));
    if (el) {
        showNameTip(el);
    } else {
        hideNameTip();
    }
}

function initNameTip() {
    document.addEventListener('mousemove', function (event) {
        tipMouseX = event.clientX;
        tipMouseY = event.clientY;
    });
    document.addEventListener('mouseover', function (event) {
        if (document.body.classList.contains('resizing')) {
            return;  // 拖拽列宽时不弹提示,避免干扰。
        }
        if (nameTipFor && !nameTipFor.isConnected) {
            hideNameTip();
        }
        var el = nameTipTarget(event.target);
        if (!el || nameTipFor === el) {
            return;
        }
        showNameTip(el);
    });
    document.addEventListener('mouseout', function (event) {
        var el = nameTipTarget(event.target);
        var to = nameTipTarget(event.relatedTarget);
        if (el && nameTipFor === el && to !== el) {
            hideNameTip();  // 仍在同一元素内移动时不隐藏,避免闪烁。
        }
    });
    window.addEventListener('scroll', hideNameTip, true);  // 滚动后位置失效,直接隐藏。
    document.addEventListener('pointerdown', function (event) {
        if (nameTipTarget(event.target) !== nameTipFor) {
            hideNameTip();  // 点击提示以外的区域时关闭。
        }
    });
}

/*
 * ===== 渐变背景实现 =====
 * 移植自 telegram-tt(web.telegram.org/a)的 util/gradientBackground.ts;
 * 该渐变算法改编自 http://useless.altervista.org/gradient.html(原脚本作者未知)。
 * 原始代码以 GNU GPL-3.0 授权,版权归相应原作者所有。
 * 移植并修改: Gentlesprite, 2026-09
 * 修改内容: 将原 React/TS 实现改写为原生 JS,并适配本项目 DOM 结构。
 * SPDX-License-Identifier: GPL-3.0-only
 */
/* ===== 渐变背景,逐行移植自官方 web.telegram.org/a(telegram-tt)的 util/gradientBackground.ts =====
   注意:官方 Web A 与 Web K(tweb)的渐变是两套实现,色点坐标、混色公式、颜色顺序都不同。 */
var BG_GRADIENT_SIZE = 100;  // 官方 useGradientBackground 的 CANVAS_SIZE = 100,靠 CSS 拉伸获得柔和观感。
var BG_GRADIENT_SPEED = 0.1;  // 官方 ANIMATION_SPEED:色点向目标点移动的每帧插值系数。
var BG_GRADIENT_EPSILON = 0.01;  // 官方 POSITION_EPSILON:色点与目标的距离小于该值视为到位。
var BG_GRADIENT_BLEND_POWER = 3;  // 官方 BLEND_POWER:按"与最近色点的距离差"加权的幂次。
var BG_GRADIENT_STEP = 2;  // 官方 KEY_POINT_STEP:每个颜色点每次前进 2 个索引。
var BG_GRADIENT_POINTS = [  // 官方 KEY_POINTS:8 个色点的归一化坐标。
    [0.265, 0.582],
    [0.176, 0.918],
    [0.415, 0.836],
    [0.644, 0.755],
    [0.735, 0.418],
    [0.824, 0.082],
    [0.585, 0.164],
    [0.356, 0.245]
];
var bgCanvas = null;
var bgCtx = null;
var bgHelperCanvas = null;  // 隐藏的小画布,先写入 ImageData 再拷贝到主画布,与官方两级结构一致。
var bgHelperCtx = null;
var bgColors = [];
var bgKeyShift = 0;
var bgCurrentPositions = [];
var bgTargetPositions = [];
var bgAnimating = false;
var bgLastProgress = -1;  // 上一轮的已完成任务总数,-1 表示尚未记录基数。
// 涂鸦遮罩烘焙相关:把 pattern.svg 光栅化后逐帧用 destination-in 烙进画布,取代 CSS mask-image,
// 从而消除 Chrome 对「带遮罩的 canvas 每帧重绘」的分块闪烁(Edge 不触发此 bug)。
var bgDoodleImg = null;     // 加载并补全尺寸的涂鸦原图。
var bgDoodlePattern = null; // 由遮罩瓦片画布生成的重复图案,用于在设备像素空间 1:1 平铺。
var bgDoodleLoader = null;  // 遮罩图加载器。
var bgDoodleDpr = 0;        // 当前瓦片所用像素密度,用于判断是否需要重建。
var bgDoodleTileW = 0;      // 遮罩瓦片宽(设备像素),对应官方 mask-size 的 26.875rem(430px)。
var bgDoodleTileH = 0;      // 遮罩瓦片高(设备像素),按原图宽高比推算。
var bgDoodleOffX = 0;       // 对应官方 mask-position:center 的平铺原点横向偏移(设备像素)。
var bgDoodleOffY = 0;       // 对应官方 mask-position:center 的平铺原点纵向偏移(设备像素)。
var BG_PATTERN_URL = 'img/pattern.svg';     // 官方涂鸦图案,与被移除的 CSS mask-image 同一文件。
var BG_PATTERN_TILE = 430;                   // 官方 26.875rem(1rem=16px)对应的瓦片宽度(CSS px)。
var BG_PATTERN_ASPECT = 2960 / 1440;         // 遮罩原图 viewBox 宽高比,取不到固有尺寸时兜底。

function bgHexToRgb(hex) {  // 把 #rrggbb 颜色解析为 [r, g, b] 数组。
    var value = parseInt(hex.slice(1, 7), 16);
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function bgGetPositions(shift) {  // 官方 buildTargetPositions:取 keyPoints[(shift + i × 2) % 8] 的 4 个点。
    var result = [];
    for (var i = 0; i < 4; i++) {
        var point = BG_GRADIENT_POINTS[(shift + i * BG_GRADIENT_STEP) % BG_GRADIENT_POINTS.length];
        result.push([point[0], point[1]]);
    }
    return result;
}

var bgImageData = null;  // 复用的 ImageData:每帧新建会产生大量 GC 压力。

function bgGetGradientImageData() {  // 官方 drawStaticGradient:按与最近色点的距离差 3 次幂加权混合四色。
    // 优化点:复用 ImageData、取消每像素的数组分配、用乘法替代 Math.pow,视觉结果完全一致。
    if (!bgImageData) {
        bgImageData = bgHelperCtx.createImageData(BG_GRADIENT_SIZE, BG_GRADIENT_SIZE);
    }
    var pixels = bgImageData.data;
    var offset = 0;
    var size = BG_GRADIENT_SIZE;
    // 色点坐标与颜色提到循环外,避免每个像素重复读取数组。
    var px0 = bgCurrentPositions[0][0], py0 = bgCurrentPositions[0][1];
    var px1 = bgCurrentPositions[1][0], py1 = bgCurrentPositions[1][1];
    var px2 = bgCurrentPositions[2][0], py2 = bgCurrentPositions[2][1];
    var px3 = bgCurrentPositions[3][0], py3 = bgCurrentPositions[3][1];
    var c0r = bgColors[0][0], c0g = bgColors[0][1], c0b = bgColors[0][2];
    var c1r = bgColors[1][0], c1g = bgColors[1][1], c1b = bgColors[1][2];
    var c2r = bgColors[2][0], c2g = bgColors[2][1], c2b = bgColors[2][2];
    var c3r = bgColors[3][0], c3g = bgColors[3][1], c3b = bgColors[3][2];
    for (var y = 0; y < size; y++) {
        var yRatio = y / size;
        // 行方向的差值在外层算一次,内层复用。
        var ay = yRatio - py0, by = yRatio - py1, cy = yRatio - py2, dy = yRatio - py3;
        var ay2 = ay * ay, by2 = by * by, cy2 = cy * cy, dy2 = dy * dy;
        for (var x = 0; x < size; x++) {
            var xRatio = x / size;
            var ax = xRatio - px0, bx = xRatio - px1, cx = xRatio - px2, dx = xRatio - px3;
            var d0 = Math.sqrt(ax * ax + ay2);
            var d1 = Math.sqrt(bx * bx + by2);
            var d2 = Math.sqrt(cx * cx + cy2);
            var d3 = Math.sqrt(dx * dx + dy2);
            var min = d0;
            if (d1 < min) {
                min = d1;
            }
            if (d2 < min) {
                min = d2;
            }
            if (d3 < min) {
                min = d3;
            }
            // 权重 = (1 - (距离 - 最近距离)) 的 BG_GRADIENT_BLEND_POWER(3) 次幂;
            // 常数 3 用连乘代替 Math.pow,速度快一个量级。
            var k0 = 1 - (d0 - min), k1 = 1 - (d1 - min);
            var k2 = 1 - (d2 - min), k3 = 1 - (d3 - min);
            var w0 = k0 * k0 * k0, w1 = k1 * k1 * k1;
            var w2 = k2 * k2 * k2, w3 = k3 * k3 * k3;
            var total = w0 + w1 + w2 + w3;
            if (total < 0) {
                total = -total;
            }
            if (total === 0) {
                total = 1;
            }  // 避免除零(原实现会产出 NaN)。
            var n0 = w0 / total, n1 = w1 / total, n2 = w2 / total, n3 = w3 / total;
            pixels[offset++] = c0r * n0 + c1r * n1 + c2r * n2 + c3r * n3;
            pixels[offset++] = c0g * n0 + c1g * n1 + c2g * n2 + c3g * n3;
            pixels[offset++] = c0b * n0 + c1b * n1 + c2b * n2 + c3b * n3;
            pixels[offset++] = 255;
        }
    }
    return bgImageData;
}

function bgDrawImageData(id) {  // 先写入隐藏画布,再拉伸拷贝到设备分辨率主画布,随后用 destination-in 烘焙涂鸦。
    var viewW = bgCanvas.width || BG_GRADIENT_SIZE;
    var viewH = bgCanvas.height || BG_GRADIENT_SIZE;
    bgHelperCtx.putImageData(id, 0, 0);
    bgCtx.save();
    bgCtx.globalCompositeOperation = 'source-over';
    bgCtx.clearRect(0, 0, viewW, viewH);
    bgCtx.imageSmoothingEnabled = true;
    bgCtx.drawImage(bgHelperCanvas, 0, 0, BG_GRADIENT_SIZE, BG_GRADIENT_SIZE, 0, 0, viewW, viewH);
    if (bgDoodlePattern) {
        /* 用 destination-in 把涂鸦烘焙进画布像素,取代 CSS mask-image:遮罩不再由浏览器合成层处理,
           每帧只剩两次全屏绘制,Chrome 不再有逐帧重合成遮罩导致的分块闪烁。
           图案在设备像素空间 1:1 平铺,不缩放,清晰度与矢量遮罩一致。 */
        bgCtx.globalCompositeOperation = 'destination-in';
        bgCtx.setTransform(1, 0, 0, 1, 0, 0);
        bgCtx.translate(bgDoodleOffX, bgDoodleOffY);
        bgCtx.fillStyle = bgDoodlePattern;
        bgCtx.fillRect(-bgDoodleOffX, -bgDoodleOffY, viewW, viewH);
    }
    bgCtx.restore();
}

function bgDoodleAspect() {  // 遮罩原图宽高比:优先取固有尺寸,退化成默认 300×150 等异常时按 viewBox 兜底。
    var width = bgDoodleImg.naturalWidth;
    var height = bgDoodleImg.naturalHeight;
    if (width > 0 && height > 0) {
        var ratio = height / width;
        if (ratio > 1.2 && ratio < 3.0) {  // 合理涂鸦宽高比区间,排除浏览器默认 300×150 退化尺寸。
            return ratio;
        }
    }
    return BG_PATTERN_ASPECT;
}

function bgBuildDoodle() {  // 把遮罩原图按当前设备像素密度光栅化为瓦片画布,再生成重复图案。
    if (!bgDoodleImg || !bgCtx) {
        return;
    }
    var dpr = window.devicePixelRatio || 1;  // 不封顶:放大时浏览器 dpr 会升高,按真实值光栅化才 1:1 清晰。
    if (bgDoodlePattern && bgDoodleDpr === dpr) {
        return;  // 像素密度未变化无需重建,避免拖动窗口时反复光栅化 SVG。
    }
    bgDoodleDpr = dpr;
    var tileW = Math.max(1, Math.round(BG_PATTERN_TILE * dpr));
    var tileH = Math.max(1, Math.round(BG_PATTERN_TILE * bgDoodleAspect() * dpr));
    var tile = document.createElement('canvas');
    tile.width = tileW;
    tile.height = tileH;
    var tileCtx = tile.getContext('2d');
    // 瓦片宽高比与 viewBox 一致,SVG 矢量按目标尺寸清晰光栅化,不会出现发虚或留白。
    tileCtx.drawImage(bgDoodleImg, 0, 0, tileW, tileH);
    bgDoodlePattern = bgCtx.createPattern(tile, 'repeat');
}

function bgUpdateDoodleGeometry() {  // 依据瓦片宽高比与画布尺寸计算居中平铺偏移(设备像素)。
    if (!bgDoodleImg || !bgCanvas) {
        return;
    }
    var dpr = window.devicePixelRatio || 1;  // 不封顶:与瓦片光栅化、画布分辨率保持一致,放大才清晰。
    bgDoodleTileW = BG_PATTERN_TILE * dpr;
    bgDoodleTileH = bgDoodleTileW * bgDoodleAspect();
    bgDoodleOffX = ((bgCanvas.width - bgDoodleTileW) / 2) % bgDoodleTileW;
    bgDoodleOffY = ((bgCanvas.height - bgDoodleTileH) / 2) % bgDoodleTileH;
}

function bgResizeCanvas() {  // 按视口设备分辨率设定主画布,并同步遮罩平铺偏移与图案,随后立即重绘。
    if (!bgCanvas || !bgCtx) {
        return;
    }
    var dpr = window.devicePixelRatio || 1;  // 不封顶:画布按真实设备分辨率建立,放大时随 resize 重建且清晰。
    var width = Math.max(1, Math.round((bgCanvas.clientWidth || window.innerWidth || 1) * dpr));
    var height = Math.max(1, Math.round((bgCanvas.clientHeight || window.innerHeight || 1) * dpr));
    if (bgCanvas.width !== width || bgCanvas.height !== height) {
        bgCanvas.width = width;  // 重设宽高会清空画布并重置状态,需重建变换。
        bgCanvas.height = height;
    }
    bgUpdateDoodleGeometry();
    bgBuildDoodle();
    bgDrawImageData(bgGetGradientImageData());
}

function bgEnsureSvgSize(text) {  // 给无固有尺寸的 SVG 补上与 viewBox 一致的 width/height,避免被缩放模糊。
    return text.replace(/<svg([^>]*)>/i, function (match, attrs) {
        if (/\bwidth\s*=/.test(attrs) && /\bheight\s*=/.test(attrs)) {
            return match;
        }
        var box = attrs.match(/viewBox\s*=\s*["']\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)/i);
        if (!box) {
            return match;
        }
        return '<svg' + attrs + ' width="' + box[1] + '" height="' + box[2] + '">';
    });
}

function bgLoadDoodle() {  // 异步加载涂鸦遮罩,就绪后烘焙进画布并显示背景,失败则退化为纯渐变。
    bgDoodleLoader = new Image();
    bgDoodleLoader.onload = function () {
        bgDoodleImg = bgDoodleLoader;
        bgUpdateDoodleGeometry();
        bgBuildDoodle();
        bgDrawImageData(bgGetGradientImageData());
        bgCanvas.classList.add('on');
        if (bgDoodleLoader.src.indexOf('blob:') === 0) {
            URL.revokeObjectURL(bgDoodleLoader.src);
        }
    };
    bgDoodleLoader.onerror = function () {  // 遮罩加载失败:退化为无涂鸦的纯渐变背景,至少不再闪。
        bgCanvas.classList.add('on');
    };
    // 直接加载无固有尺寸的 SVG 会让浏览器退化成 300×150 再放大,导致涂鸦模糊;
    // 故先取文本、补上与 viewBox 一致的 width/height 再生成 Blob URL,确保按目标尺寸清晰光栅化。
    if (typeof fetch === 'function') {
        fetch(BG_PATTERN_URL).then(function (response) {
            return response.text();
        }).then(function (text) {
            var blob = new Blob([bgEnsureSvgSize(text)], {type: 'image/svg+xml'});
            bgDoodleLoader.src = URL.createObjectURL(blob);
        }).catch(function () {
            bgDoodleLoader.src = BG_PATTERN_URL;  // 取文本失败则退回直接加载(可能发虚,仅兜底)。
        });
    } else {
        bgDoodleLoader.src = BG_PATTERN_URL;
    }
}

function bgStepPositions() {  // 官方 stepPositions:色点向目标点做 0.1 线性插值,到位后停止。
    var moving = false;
    for (var i = 0; i < 4; i++) {
        var current = bgCurrentPositions[i];
        var target = bgTargetPositions[i];
        if (Math.abs(current[0] - target[0]) > BG_GRADIENT_EPSILON
            || Math.abs(current[1] - target[1]) > BG_GRADIENT_EPSILON) {
            moving = true;
        }
        current[0] = current[0] * (1 - BG_GRADIENT_SPEED) + target[0] * BG_GRADIENT_SPEED;
        current[1] = current[1] * (1 - BG_GRADIENT_SPEED) + target[1] * BG_GRADIENT_SPEED;
    }
    return moving;
}

function bgAnimate() {  // 官方 animate:仅在色点移动期间逐帧重绘,静止后自动停止,开销几乎为零。
    var moving = bgStepPositions();
    bgDrawImageData(bgGetGradientImageData());
    if (moving) {
        requestAnimationFrame(bgAnimate);
    } else {
        bgAnimating = false;
    }
}

function bgAdvancePosition() {  // 官方 advancePosition:推进到下一个目标位并启动补间;官方在发送消息时调用。
    bgTargetPositions = bgGetPositions(bgKeyShift);
    bgKeyShift = (bgKeyShift + 1) % BG_GRADIENT_POINTS.length;
    if (!bgAnimating) {
        bgAnimating = true;
        requestAnimationFrame(bgAnimate);
    }
}

function initBackgroundGradient() {
    bgCanvas = document.getElementById('bgGradient');
    if (!bgCanvas || !bgCanvas.getContext) {
        return;
    }
    bgHelperCanvas = document.createElement('canvas');
    bgHelperCanvas.width = BG_GRADIENT_SIZE;
    bgHelperCanvas.height = BG_GRADIENT_SIZE;
    bgHelperCtx = bgHelperCanvas.getContext('2d', {alpha: false});
    var colors = (bgCanvas.getAttribute('data-colors') || '').split(',');
    for (var i = 0; i < colors.length; i++) {
        var color = colors[i].trim();
        if (/^#[0-9a-fA-F]{6}$/.test(color)) {
            bgColors.push(bgHexToRgb(color));
        }
    }
    if (!bgColors.length) {
        return;
    }
    // 官方初始布点为 keyPoints[0,2,4,6],首个目标与当前位置相同,因此加载后与官方静止状态一致。
    bgCurrentPositions = bgGetPositions(0);
    bgTargetPositions = bgGetPositions(0);
    bgKeyShift = 1;
    // 启用 alpha:涂鸦以外区域透明,露出页面底色,观感与原 CSS mask 一致。
    bgCtx = bgCanvas.getContext('2d', {alpha: true});
    bgResizeCanvas();  // 按设备分辨率建立主画布并完成首次绘制(此时尚无涂鸦,仅渐变)。
    window.addEventListener('resize', bgResizeCanvas);
    bgLoadDoodle();  // 遮罩就绪后再添加 on 类显示背景,避免未遮罩的全屏渐变闪现。
}

bindSections();
bindListenTabs();
bindStorageTabs();
bindStorageHover();
bindStoragePager();
bindStorageFilters();
bindListenRemove();
bindConfirm();
bindLogin();
initLogout();
bindStatFilter();
bindSupport();
bindMenu();
initSettings();
initVersion();
loadStorageFilters();  // 先恢复筛选条件,下面重建表头时才带得出漏斗激活态。
currentStorage = STORAGE_TABS.indexOf(savedStorage) > -1 ? savedStorage : 'download';
applyStorageTab();  // 先按保存的选项刷新高亮,此时尚未拉取数据,列表保持空态。
applySectionVisibility();  // 按可用功能调整侧边栏,随后switchSection会锁定到可用的页面。
switchSection(savedSection);
switchListen(savedListen);
document.getElementById('toggleAll').onclick = toggleAll;
document.getElementById('toggleUpload').onclick = toggleUploadAll;
initCols();  // 恢复上次的列宽并生成拖拽分隔条。
bindPause();  // 绑定全局暂停/恢复按钮。
initNameTip();  // 悬停文件名时显示完整名称。
initBackgroundGradient();  // 启动 Telegram 风格的动画渐变背景。

/* 页面不可见(切到后台标签/最小化)时暂停轮询。
   后台标签不会被合成显示,继续每秒拉取数据、比对指纹、重建 DOM 只是白白吃 CPU;
   回到前台时立即补一次刷新,观感完全不受影响。 */
var pollTimer = 0;

function startPolling() {
    if (!pollTimer) {
        pollTimer = setInterval(refresh, POLL_INTERVAL_MS);
    }
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = 0;
    }
}

document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
        stopPolling();
    } else {
        refresh();  // 回到前台先补一次,避免看到后台期间滞留的旧数据。
        startPolling();
    }
});

refresh(true);  // 首屏强制按最新数据渲染,跳过去重,确保进度条开局即正确显示。
startPolling();
startStoragePolling();  // 记录页轮询:内部按当前区块判断,只有停留在记录页才真正查询数据库。

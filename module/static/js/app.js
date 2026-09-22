/* TRMD Web UI — 前端脚本(含从 telegram-tt 移植的渐变背景实现)
 * Copyright © 2024-2026 Gentlesprite
 * SPDX-License-Identifier: GPL-3.0-only
 * 本文件整体以 GNU GPL-3.0 授权;完整许可见仓库根目录 LICENCE。
 */
const EMPTY_SUMMARY = {percent: 0, info: '0.00B / 0.00B', speed: '', remaining: ''};

var SECTIONS = {
    download: ['download'],
    upload: ['upload'],
    listener: ['listener']
};
var PAGES = SECTIONS.download.concat(SECTIONS.upload, SECTIONS.listener);  // 下载、上传各一个页面,监听页只在内部切换选项卡。
var SUMMARY_IDS = {
    download: {fill: 'overallFill', percent: 'overallPercent', info: 'overallInfo', extra: 'overallExtra'},
    upload: {fill: 'uploadFill', percent: 'uploadPercent', info: 'uploadInfo', extra: 'uploadExtra'}
};  // 下载与上传各自独立的总进度面板,避免相互覆盖。
var SECTION_KEY = 'trmd_section';
var LISTEN_KEY = 'trmd_listen';
var HAS_BOT = document.body.getAttribute('data-bot') === '1';  // 是否配置了机器人,决定上传/监听侧边栏是否展示(无机器人时只有下载可用)。
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
var lastDownloadActive = 0;
var lastUploadActive = 0;
var lastListenCount = 0;
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
    var nodes = document.querySelectorAll('.group-head');
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
}

function switchSection(name) {
    if (!SECTIONS[name]) {
        name = 'download';
    }
    if (!HAS_BOT && name !== 'download') {  // 未配置机器人时仅允许下载页,避免停留在不可用的上传/监听页。
        name = 'download';
    }
    currentSection = name;
    applySection();
    saveState(SECTION_KEY, currentSection);
}

function applyBotVisibility() {
    // 未配置机器人时只有下载一个功能,无需用侧边栏区分页面,直接隐藏整个侧边栏并将布局退化为单栏。
    if (HAS_BOT) {
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
        render(await res.json(), force);
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

function supportMaskClick(event) {
    if (event.target === this) {  // 点击遮罩空白处关闭弹窗。
        closeSupport();
    }
}

function supportEscape(event) {
    if (event.key === 'Escape' && !document.getElementById('supportModal').hidden) {
        closeSupport();
    }
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
    document.getElementById('supportModal').onclick = supportMaskClick;
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
// 返回数组与表头列格一一对应,首项为弹性列(频道/监听频道)的下限。
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

function applyCols(list, widths, flexMin) {
    var parts = ['minmax(' + (flexMin || COLS_MIN) + 'px, 1fr)'];  // 首列弹性列不低于标题宽度,避免被其它列挤到看不见。
    for (var i = 0; i < widths.length; i++) {
        parts.push(widths[i] + 'px');
    }
    list.style.setProperty('--cols', parts.join(' '));
}

function buildGrips(list) {
    var head = list.querySelector('.list-head');
    var cells = head.children;
    var table = list.getAttribute('data-table');
    for (var i = 0; i < cells.length - 1; i++) {  // 末列格右侧为容器边界,不生成分隔条。
        if (cells[i].querySelector('.grip')) {
            continue;  // 已存在分隔条时不重复创建。
        }
        var grip = document.createElement('span');
        grip.className = 'grip';
        grip.setAttribute('data-table', table);
        grip.setAttribute('data-index', i);
        grip.onpointerdown = resizeStart;
        cells[i].appendChild(grip);
    }
}

function clampColsWidth(widths, index, value, maxFixed, mins) {
    var others = 0;
    for (var i = 0; i < widths.length; i++) {
        if (i !== index) {
            others += widths[i];
        }
    }
    // 下限取标题完整显示所需宽度,保证表头标题永不被压缩。
    var floor = Math.max(COLS_MIN, (mins && mins[index + 1]) || COLS_MIN);
    // 预留首列弹性列的最小宽度,避免固定列被拉到超出可用空间后挤压首列文字。
    var flexMin = flexColMin(mins && mins[0]);
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
        sign: -1,  // 向右拖动缩小该列(空间让给首列弹性列),向左拖动加宽;分隔条始终跟随光标。
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
    dragState.widths[dragState.col] = clampColsWidth(dragState.widths, dragState.col, value, dragState.maxFixed, dragState.mins);
    applyCols(dragState.list, dragState.widths, flexColMin(dragState.mins[0]));
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
        var widths = colsCache[table];
        if (!widths || widths.length !== head.children.length - 1) {
            widths = readDefaultCols(list);  // 列数变化或首次加载时回退到默认列宽。
        }
        var mins = measureColMins(list);
        var j;
        for (j = 0; j < widths.length; j++) {
            widths[j] = Math.max(widths[j], mins[j + 1]);  // 已保存的列宽也不得小于标题所需宽度。
        }
        colsCache[table] = widths;
        applyCols(list, widths, flexColMin(mins[0]));
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
try {
    savedSection = localStorage.getItem(SECTION_KEY) || '';
    savedListen = localStorage.getItem(LISTEN_KEY) || '';
    collapsed = JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '{}') || {};  // 读回各分组折叠状态。
    allCollapsed = localStorage.getItem(ALL_KEY) === '1';
    uploadAllCollapsed = localStorage.getItem(UPLOAD_ALL_KEY) === '1';
    lastLinkCollapsed = localStorage.getItem(LINK_LAST_KEY) !== '0';  // 无记录时保持链接层默认折叠。
    lastUploadCollapsed = localStorage.getItem(UPLOAD_LAST_KEY) === '1';  // 无记录时保持上传频道层默认展开。
} catch (e) {
    savedSection = '';
    savedListen = '';
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
bindListenRemove();
bindConfirm();
bindLogin();
initLogout();
bindStatFilter();
bindSupport();
bindMenu();
initVersion();
applyBotVisibility();  // 未配置机器人时隐藏整个侧边栏,随后switchSection会强制锁定到下载页。
switchSection(savedSection);
switchListen(savedListen);
document.getElementById('toggleAll').onclick = toggleAll;
document.getElementById('toggleUpload').onclick = toggleUploadAll;
initCols();  // 恢复上次的列宽并生成拖拽分隔条。
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

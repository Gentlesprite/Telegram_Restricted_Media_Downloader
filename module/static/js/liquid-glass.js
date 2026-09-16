/* 液态玻璃(Liquid Glass)效果实现。
 * 移植自 liquid-glass 项目:
 * MIT license Copyright (c) 2025 Nikita Stadnik <https://github.com/nikdelvin/liquid-glass>,
 * 将 SVG 位移贴图(displacement map)注入 backdrop-filter,
 * 让卡片边缘产生折射般的玻璃厚度感,而非普通毛玻璃的均匀模糊。
 * 实现方式:在 DOM 中维护内联 <svg> 滤镜,卡片通过 backdrop-filter: url(#id) 引用,
 * 该方式在 Chromium 内核浏览器中可靠生效(比整段滤镜塞进 data URI 更稳定)。
 *
 * 性能约定:该滤镜开销较大,因此做了以下优化——
 * 1) 滤镜按尺寸与参数缓存复用,尺寸相同的元素(如所有分组标题)共用同一个滤镜;
 * 2) 重绘合并到下一帧,尺寸未变时直接跳过;
 * 3) 无色散时只做一次位移,不做 RGB 三通道分离。
 * 这样即使列表内部元素较多,也不会每次刷新都重新生成滤镜。 */

const LG_NS = 'http://www.w3.org/2000/svg';
const LG_STEP = 4;   // 尺寸取整步长,邻近尺寸复用同一滤镜,避免频繁重建。
const LG_MAX_CACHE = 80;  // 滤镜缓存上限,超出后整体重建,避免节点无限增长。

const lgCache = new Map();    // 参数 -> 已创建的滤镜 id。
const lgPending = new Set();  // 待重绘元素,合并到下一帧统一处理。
let lgFrame = 0;
let lgSeq = 0;

// 生成位移贴图:一张用于驱动 feDisplacementMap 的 RGB 渐变图,边缘形成玻璃斜面。
function lgGetDisplacementMap(opts) {
    const { height, width, radius, depth } = opts;
    const safeRadius = isFinite(radius) ? radius : 0;
    const svg =
        '<svg height="' + height + '" width="' + width + '" viewBox="0 0 ' + width + ' ' + height + '" xmlns="http://www.w3.org/2000/svg">' +
        '<style>.mix { mix-blend-mode: screen; }</style>' +
        '<defs>' +
        '<linearGradient id="Y" x1="0" x2="0" y1="' + Math.ceil((safeRadius / height) * 15) + '%" y2="' + Math.floor(100 - (safeRadius / height) * 15) + '%">' +
        '<stop offset="0%" stop-color="#0F0" /><stop offset="100%" stop-color="#000" />' +
        '</linearGradient>' +
        '<linearGradient id="X" x1="' + Math.ceil((safeRadius / width) * 15) + '%" x2="' + Math.floor(100 - (safeRadius / width) * 15) + '%" y1="0" y2="0">' +
        '<stop offset="0%" stop-color="#F00" /><stop offset="100%" stop-color="#000" />' +
        '</linearGradient>' +
        '</defs>' +
        '<rect x="0" y="0" height="' + height + '" width="' + width + '" fill="#808080" />' +
        '<g filter="blur(2px)">' +
        '<rect x="0" y="0" height="' + height + '" width="' + width + '" fill="#000080" />' +
        '<rect x="0" y="0" height="' + height + '" width="' + width + '" fill="url(#Y)" class="mix" />' +
        '<rect x="0" y="0" height="' + height + '" width="' + width + '" fill="url(#X)" class="mix" />' +
        '<rect x="' + depth + '" y="' + depth + '" height="' + (height - 2 * depth) + '" width="' + (width - 2 * depth) + '" fill="#808080" rx="' + safeRadius + '" ry="' + safeRadius + '" filter="blur(' + depth + 'px)" />' +
        '</g>' +
        '</svg>';
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
}

// 生成滤镜内部 SVG:以位移贴图驱动 feDisplacementMap 扭曲背景。
// 无色散时只做一次位移;有色散时才分离 RGB 三通道分别位移再混合,避免默认配置下白跑两遍位移。
function lgGetFilterInner(opts) {
    const { height, width, radius, depth, strength = 100, chromaticAberration = 0 } = opts;
    const map = lgGetDisplacementMap({ height, width, radius, depth });
    const image = '<feImage x="0" y="0" height="' + height + '" width="' + width + '" href="' + map + '" result="displacementMap" />';
    if (!chromaticAberration) {
        return image +
            '<feDisplacementMap in="SourceGraphic" in2="displacementMap" scale="' + strength + '" xChannelSelector="R" yChannelSelector="G" />';
    }
    return image +
        '<feDisplacementMap in="SourceGraphic" in2="displacementMap" scale="' + (strength + chromaticAberration * 2) + '" xChannelSelector="R" yChannelSelector="G" />' +
        '<feColorMatrix type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="displacedR" />' +
        '<feDisplacementMap in="SourceGraphic" in2="displacementMap" scale="' + (strength + chromaticAberration) + '" xChannelSelector="R" yChannelSelector="G" />' +
        '<feColorMatrix type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="displacedG" />' +
        '<feDisplacementMap in="SourceGraphic" in2="displacementMap" scale="' + strength + '" xChannelSelector="R" yChannelSelector="G" />' +
        '<feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="displacedB" />' +
        '<feBlend in="displacedR" in2="displacedG" mode="screen" />' +
        '<feBlend in2="displacedB" mode="screen" />';
}

// 检测浏览器是否支持 backdrop-filter: url(#...)。
const lgSupportsUrl = (function () {
    const el = document.createElement('div');
    el.style.cssText = 'backdrop-filter: url(#test)';
    return el.style.backdropFilter === 'url(#test)' || el.style.backdropFilter === 'url("#test")';
})();

// 获取/创建内联滤镜容器,所有滤镜都挂在这里,供卡片以 url(#id) 引用。
function lgGetDefs() {
    let svg = document.getElementById('lg-svg');
    if (!svg) {
        svg = document.createElementNS(LG_NS, 'svg');
        svg.id = 'lg-svg';
        svg.setAttribute('style', 'position:absolute;width:0;height:0;overflow:hidden;pointer-events:none;');
        const defs = document.createElementNS(LG_NS, 'defs');
        svg.appendChild(defs);
        document.body.appendChild(svg);
    }
    return svg.querySelector('defs');
}

// 清空滤镜缓存,并让已应用的元素在下一帧重新取用滤镜。
function lgResetCache() {
    lgCache.clear();
    const defs = lgGetDefs();
    while (defs.firstChild) {
        defs.removeChild(defs.firstChild);
    }
    document.querySelectorAll('[data-lg-size]').forEach(function (el) {
        el.removeAttribute('data-lg-size');
    });
}

// 按参数取用共享滤镜:尺寸与参数相同的卡片共用同一个滤镜节点。
function lgFilterId(opts) {
    const key = [opts.width, opts.height, opts.radius, opts.depth, opts.strength, opts.cab].join('|');
    const hit = lgCache.get(key);
    if (hit) {
        return hit;
    }
    if (lgCache.size >= LG_MAX_CACHE) {
        lgResetCache();
    }
    const id = 'lg-glass-' + (++lgSeq);
    const filter = document.createElementNS(LG_NS, 'filter');
    filter.id = id;
    filter.setAttribute('color-interpolation-filters', 'sRGB');
    // 扩张滤镜区域,避免边缘折射被裁切。
    filter.setAttribute('x', '-20%');
    filter.setAttribute('y', '-20%');
    filter.setAttribute('width', '140%');
    filter.setAttribute('height', '140%');
    filter.innerHTML = lgGetFilterInner({
        height: opts.height,
        width: opts.width,
        radius: opts.radius,
        depth: opts.depth,
        strength: opts.strength,
        chromaticAberration: opts.cab
    });
    lgGetDefs().appendChild(filter);
    lgCache.set(key, id);
    return id;
}

// 根据元素尺寸与边框圆角,重算并应用液态玻璃的背景滤镜。
function lgRedraw(glass) {
    const rect = glass.getBoundingClientRect();
    if (!rect.width || !rect.height) {
        return;  // 未参与布局(如处于隐藏面板)时跳过,避免生成无效滤镜。
    }
    const width = Math.max(LG_STEP, Math.round(rect.width / LG_STEP) * LG_STEP);
    const height = Math.max(LG_STEP, Math.round(rect.height / LG_STEP) * LG_STEP);
    const sizeKey = width + 'x' + height;
    if (glass.dataset.lgSize === sizeKey) {
        return;  // 尺寸未变化,沿用现有滤镜,不重复生成。
    }
    glass.dataset.lgSize = sizeKey;

    const cs = getComputedStyle(glass);
    // 圆角限制在短边一半以内,避免胶囊形卡片折射过强。
    const radius = Math.round(Math.min(parseFloat(cs.borderRadius) || 0, Math.min(width, height) / 2));
    // 饱和度与亮度沿用主题变量,与页面其它毛玻璃同色;
    // 模糊半径单独取 --liquid-blur,保持较小值,折射边缘才锐利(改大就会糊成普通毛玻璃)。
    const root = getComputedStyle(document.documentElement);
    const glassBlur = (root.getPropertyValue('--glass-blur') || '26px').trim();
    const liquidBlur = parseFloat(glass.dataset.lgBlur || root.getPropertyValue('--liquid-blur')) || 2;
    const saturate = (glass.dataset.lgSaturate || root.getPropertyValue('--glass-saturate') || '190%').trim();
    const brightness = (glass.dataset.lgBrightness || root.getPropertyValue('--glass-brightness') || '1').trim();
    const depth = parseFloat(glass.dataset.lgDepth || '4');
    const strength = parseFloat(glass.dataset.lgStrength || '140');
    const cab = parseFloat(glass.dataset.lgCab || '0');
    const bf = 'saturate(' + saturate + ') brightness(' + brightness + ')';

    if (!lgSupportsUrl) {
        // 不支持时回退为普通毛玻璃,保留上沿高光与淡投影以维持质感。
        glass.style.backdropFilter = 'blur(' + glassBlur + ') ' + bf;
        glass.style.webkitBackdropFilter = 'blur(' + glassBlur + ') ' + bf;
        glass.style.boxShadow = 'inset 0 1px 0 rgba(255, 255, 255, .06), 0 4px 16px rgba(0, 0, 0, .28)';
        return;
    }

    // 位移前后各一次轻模糊:先柔化再折射、再收边,这是液态玻璃质感的关键。
    const half = liquidBlur / 2;
    const value = 'blur(' + half + 'px) url(#' + lgFilterId({
        width: width, height: height, radius: radius,
        depth: depth, strength: strength, cab: cab
    }) + ') blur(' + half + 'px) ' + bf;
    glass.style.backdropFilter = value;
    glass.style.webkitBackdropFilter = value;
}

// 把重绘合并到下一帧,避免同一帧内多次尺寸变化重复生成滤镜。
function lgSchedule(glass) {
    lgPending.add(glass);
    if (lgFrame) {
        return;
    }
    lgFrame = requestAnimationFrame(function () {
        lgFrame = 0;
        lgPending.forEach(function (item) {
            lgRedraw(item);
        });
        lgPending.clear();
    });
}

// 为单个元素应用效果并监听尺寸变化,已绑定过的元素直接跳过。
function lgBind(glass) {
    if (glass.dataset.lgBound) {
        return;  // 避免数据刷新重建后重复绑定出多个 ResizeObserver。
    }
    glass.dataset.lgBound = '1';
    lgRedraw(glass);
    const ro = new ResizeObserver(function () {
        lgSchedule(glass);
    });
    ro.observe(glass);
}

// 初始化:对界面的卡片与面板统一应用效果,使整体风格一致。
function lgInit() {
    // 侧栏板块、总进度面板、监听选项卡、列表、分组标题、表头列格。
    document.querySelectorAll(
        '.side-item, .panel, .tab, .list, .group-head, .list-head > span:not(.grip)'
    ).forEach(lgBind);

    // 统计状态卡(.stat div)由脚本动态生成,通过容器监听追加。
    document.querySelectorAll('.stat').forEach(function (container) {
        container.querySelectorAll('.stat div').forEach(lgBind);
        const mo = new MutationObserver(function () {
            container.querySelectorAll('.stat div').forEach(lgBind);
        });
        mo.observe(container, { childList: true });
    });

    // 分组标题(.group-head)随数据刷新重建,监听列表变化追加效果。
    document.querySelectorAll('.list').forEach(function (list) {
        list.querySelectorAll('.group-head').forEach(lgBind);
        const mo = new MutationObserver(function () {
            list.querySelectorAll('.group-head').forEach(lgBind);
        });
        mo.observe(list, { childList: true, subtree: true });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', lgInit);
} else {
    lgInit();
}

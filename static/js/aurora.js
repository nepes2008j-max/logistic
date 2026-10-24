/* Aurora intro — a vanilla WebGL2 port of the react-bits "Aurora" background,
   tuned to Global Trade's blue palette. It mounts behind the hero text, rises
   in as the page opens, holds, then fades out and tears itself down so nothing
   keeps the GPU busy. Pure enhancement: no WebGL2, or prefers-reduced-motion,
   and the hero just shows its plain sky gradient.

   The shader (snoise aurora curtains, OKLCH colour ramp) is lifted verbatim
   from react-bits (github.com/DavidHDev/react-bits, MIT); only the React
   lifecycle around it is rewritten as plain JS. */
(function () {
    'use strict';

    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var mount = document.querySelector('.aurora-mount');
    if (!mount) return;

    // --- tuning: the site's blues, with a teal shimmer for aurora character --
    var COLOR_STOPS = ['#0B63FF', '#38E1C6', '#5AA0FF'];
    var AMPLITUDE = 1.0, BLEND = 0.5, HEIGHT = 0.5, SCALE = 1.0,
        GLOW = 0.6, BRIGHTNESS = 0.85, LAYERS = 2, SPEED = 0.9, OPACITY = 0.8;
    var INTRO_SECONDS = 2.4;
    var LIFE_MS = 7000;   // total time on screen; the CSS fade matches this

    var MAX_STOPS = 5;
    var VERTEX = '#version 300 es\nin vec2 aPosition;\nvoid main(){gl_Position=vec4(aPosition,0.0,1.0);}';
    var FRAGMENT = '#version 300 es\n'
      + 'precision highp float;precision highp int;'
      + 'uniform vec2 uResolution;uniform float uTime;uniform vec3 uStops[' + MAX_STOPS + '];'
      + 'uniform int uStopCount;uniform float uAmplitude;uniform float uBlend;uniform float uHeight;'
      + 'uniform float uScale;uniform float uGlow;uniform float uBrightness;uniform int uLayers;'
      + 'uniform float uFlip;uniform vec3 uPointer;uniform float uReveal;uniform float uOpacity;'
      + 'uniform float uLightMode;out vec4 outColor;'
      + 'vec3 permute(vec3 x){return mod(((x*34.0)+1.0)*x,289.0);}'
      + 'float snoise(vec2 v){const vec4 C=vec4(0.211324865405187,0.366025403784439,-0.577350269189626,0.024390243902439);'
      + 'vec2 i=floor(v+dot(v,C.yy));vec2 x0=v-i+dot(i,C.xx);'
      + 'vec2 i1=(x0.x>x0.y)?vec2(1.0,0.0):vec2(0.0,1.0);vec4 x12=x0.xyxy+C.xxzz;x12.xy-=i1;i=mod(i,289.0);'
      + 'vec3 p=permute(permute(i.y+vec3(0.0,i1.y,1.0))+i.x+vec3(0.0,i1.x,1.0));'
      + 'vec3 m=max(0.5-vec3(dot(x0,x0),dot(x12.xy,x12.xy),dot(x12.zw,x12.zw)),0.0);m=m*m;m=m*m;'
      + 'vec3 x=2.0*fract(p*C.www)-1.0;vec3 h=abs(x)-0.5;vec3 ox=floor(x+0.5);vec3 a0=x-ox;'
      + 'm*=1.79284291400159-0.85373472095314*(a0*a0+h*h);vec3 g;g.x=a0.x*x0.x+h.x*x0.y;'
      + 'g.yz=a0.yz*x12.xz+h.yz*x12.yw;return 130.0*dot(m,g);}'
      + 'float smootherstep(float e0,float e1,float x){float t=clamp((x-e0)/(e1-e0),0.0,1.0);return t*t*t*(t*(t*6.0-15.0)+10.0);}'
      + 'vec3 oklabToLinear(vec3 c){float l=c.x+0.3963377774*c.y+0.2158037573*c.z;float m=c.x-0.1055613458*c.y-0.0638541728*c.z;'
      + 'float s=c.x-0.0894841775*c.y-1.2914855480*c.z;l=l*l*l;m=m*m*m;s=s*s*s;'
      + 'return vec3(4.0767416621*l-3.3077115913*m+0.2309699292*s,-1.2684380046*l+2.6097574011*m-0.3413193965*s,'
      + '-0.0041960863*l-0.7034186147*m+1.7076147010*s);}'
      + 'vec3 toSrgb(vec3 c){c=clamp(c,0.0,1.0);return mix(c*12.92,1.055*pow(c,vec3(1.0/2.4))-0.055,step(0.0031308,c));}'
      + 'vec3 ramp(float t){float x=clamp(t,0.0,1.0)*float(uStopCount-1);int i=int(min(floor(x),float(uStopCount-2)));'
      + 'float f=x-float(i);f=f*f*(3.0-2.0*f);vec3 lch=mix(uStops[i],uStops[i+1],f);lch.x=mix(lch.x,min(lch.x,0.7),uLightMode);'
      + 'return toSrgb(oklabToLinear(vec3(lch.x,lch.y*cos(lch.z),lch.y*sin(lch.z))));}'
      + 'float hash(vec2 p){p=fract(p*vec2(123.34,456.21));p+=dot(p,p+45.32);return fract(p.x*p.y);}'
      + 'void main(){vec2 frag=gl_FragCoord.xy;float y=1.0-frag.y/uResolution.y;y=mix(y,1.0-y,uFlip);'
      + 'float u=frag.x/uResolution.x;float X=(frag.x-uResolution.x*0.5)/uResolution.y;float t=uTime;'
      + 'float reach=uPointer.z*exp(-pow((X-uPointer.x)/0.38,2.0));vec3 glow=vec3(0.0);float cover=0.0;'
      + 'for(int k=0;k<3;k++){if(k>=uLayers)break;float layer=float(k);float seed=layer*13.7;float pace=t*(1.0-layer*0.18);'
      + 'float warp=snoise(vec2(X*0.45*uScale+pace*0.02+seed,pace*0.05+seed));'
      + 'float wave=snoise(vec2(X*0.75*uScale+warp*0.35-pace*0.03+seed,pace*0.07-seed))*0.72'
      + '+snoise(vec2(X*1.6*uScale+warp*0.5+pace*0.04-seed,pace*0.1+seed*0.5))*0.28;'
      + 'float hem=uHeight+layer*0.07+wave*0.15*uAmplitude;hem+=reach*0.08*(layer<0.5?1.0:0.4);hem=mix(-0.25,hem,uReveal);'
      + 'float soft=(0.04+uBlend*0.16)*(1.0+layer*0.9);float rise=hem-y;float low=-soft-uGlow*0.14;float high=0.26+soft*0.6;'
      + 'float body=pow(smootherstep(low,high,rise),1.5+uGlow*0.6);'
      + 'float lobes=0.86+0.14*snoise(vec2(X*0.9*uScale-pace*0.025+seed,y*0.3+pace*0.04));'
      + 'float alpha=body*lobes*(layer<0.5?1.0:0.32/layer);'
      + 'alpha=clamp(alpha*(1.0+reach*0.25*smootherstep(0.9,0.0,abs(y-hem))),0.0,1.0);'
      + 'vec3 tint=ramp(u+0.05*sin(pace*0.08+layer*2.3)+layer*0.1+max(rise,0.0)*0.05);'
      + 'glow=1.0-(1.0-glow)*(1.0-tint*alpha);cover=1.0-(1.0-cover)*(1.0-alpha);}'
      + 'float fade=smootherstep(0.0,0.7,uReveal)*uOpacity;float strength=clamp(uBrightness,0.0,2.0);'
      + 'glow*=fade*min(strength,1.0);cover*=fade*min(strength,1.0);glow=1.0-pow(1.0-glow,vec3(max(strength,1.0)));'
      + 'float dither=(hash(frag)-0.5)/255.0;'
      + 'if(uLightMode>0.5){vec3 tint=cover>0.0001?glow/cover:vec3(0.0);cover*=smootherstep(0.0,0.25,cover);'
      + 'float alpha=cover*0.7;outColor=vec4(tint*alpha+dither,clamp(alpha+dither,0.0,1.0));return;}'
      + 'outColor=vec4(glow+dither,clamp(cover+dither,0.0,1.0));}';

    // --- colour conversion (sRGB hex -> OKLCH), ported from the component -----
    function toOklch(rgb) {
        var lin = rgb.map(function (c) { return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); });
        var r = lin[0], g = lin[1], b = lin[2];
        var l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
        var m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
        var s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
        var L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
        var A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
        var B = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
        return [L, Math.hypot(A, B), Math.atan2(B, A)];
    }
    function unwrapHues(stops) {
        var known = -1;
        for (var j = 0; j < stops.length; j++) { if (stops[j][1] > 0.02) { known = j; break; } }
        var prev = known === -1 ? 0 : stops[known][2];
        return stops.map(function (st) {
            var hue = st[1] > 0.02 ? st[2] : prev;
            while (hue - prev > Math.PI) hue -= Math.PI * 2;
            while (hue - prev < -Math.PI) hue += Math.PI * 2;
            prev = hue;
            return [st[0], st[1], hue];
        });
    }
    var probe = document.createElement('canvas').getContext('2d');
    function parse(value) {
        var rgb = [1, 1, 1];
        if (probe) {
            probe.clearRect(0, 0, 1, 1);
            probe.fillStyle = '#ffffff';
            probe.fillStyle = value;
            probe.fillRect(0, 0, 1, 1);
            var d = probe.getImageData(0, 0, 1, 1).data;
            rgb = [d[0] / 255, d[1] / 255, d[2] / 255];
        }
        return rgb;
    }

    function compile(gl, type, src) {
        var sh = gl.createShader(type);
        gl.shaderSource(sh, src);
        gl.compileShader(sh);
        if (gl.getShaderParameter(sh, gl.COMPILE_STATUS)) return sh;
        gl.deleteShader(sh);
        return null;
    }

    var canvas = document.createElement('canvas');
    canvas.className = 'aurora-canvas';
    canvas.setAttribute('aria-hidden', 'true');
    mount.appendChild(canvas);

    var gl = canvas.getContext('webgl2', {
        alpha: true, premultipliedAlpha: true, antialias: false, depth: false, stencil: false
    });
    if (!gl) { mount.remove(); return; }

    var vs = compile(gl, gl.VERTEX_SHADER, VERTEX);
    var fs = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT);
    var program = gl.createProgram();
    if (!vs || !fs) { mount.remove(); return; }
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.bindAttribLocation(program, 0, 'aPosition');
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) { mount.remove(); return; }

    var u = {};
    var n = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS);
    for (var i = 0; i < n; i++) {
        var info = gl.getActiveUniform(program, i);
        if (info) u[info.name.replace('[0]', '')] = gl.getUniformLocation(program, info.name);
    }

    var buffer = gl.createBuffer();
    var vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    var palette = new Float32Array(MAX_STOPS * 3);
    unwrapHues(COLOR_STOPS.map(function (v) { return toOklch(parse(v)); }))
        .forEach(function (stop, idx) { palette.set(stop, idx * 3); });

    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    function resize() {
        var w = Math.max(1, mount.clientWidth), h = Math.max(1, mount.clientHeight);
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
    }
    resize();
    window.addEventListener('resize', resize, { passive: true });

    var clock = 0, last = 0, reveal = 0, raf = 0, dead = false;
    function render() {
        gl.viewport(0, 0, canvas.width, canvas.height);
        gl.useProgram(program);
        gl.bindVertexArray(vao);
        gl.uniform2f(u.uResolution, canvas.width, canvas.height);
        gl.uniform1f(u.uTime, clock);
        gl.uniform3fv(u.uStops, palette);
        gl.uniform1i(u.uStopCount, COLOR_STOPS.length);
        gl.uniform1f(u.uAmplitude, AMPLITUDE);
        gl.uniform1f(u.uBlend, BLEND);
        gl.uniform1f(u.uHeight, HEIGHT);
        gl.uniform1f(u.uScale, SCALE);
        gl.uniform1f(u.uGlow, GLOW);
        gl.uniform1f(u.uBrightness, BRIGHTNESS);
        gl.uniform1i(u.uLayers, LAYERS);
        gl.uniform1f(u.uFlip, 0);
        gl.uniform3f(u.uPointer, 0, 0.5, 0);
        gl.uniform1f(u.uReveal, 1 - Math.pow(1 - reveal, 3));
        gl.uniform1f(u.uOpacity, OPACITY);
        // A dark page (dark theme) wants the additive path; a light page wants
        // the premultiplied light path so the curtains read over white.
        gl.uniform1f(u.uLightMode, document.documentElement.getAttribute('data-theme') === 'dark' ? 0 : 1);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    function frame(now) {
        if (dead) return;
        var dt = last ? Math.min(0.05, (now - last) / 1000) : 1 / 60;
        last = now;
        if (!document.hidden) {
            clock += dt * SPEED;
            if (reveal < 1) reveal = Math.min(1, reveal + dt / INTRO_SECONDS);
            render();
        }
        raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);

    // Tear down after the intro so nothing keeps rendering. The CSS fade on
    // .aurora-mount handles the visual disappearance; this frees the context.
    setTimeout(function destroy() {
        dead = true;
        cancelAnimationFrame(raf);
        window.removeEventListener('resize', resize);
        gl.deleteProgram(program);
        gl.deleteBuffer(buffer);
        gl.deleteVertexArray(vao);
        var lose = gl.getExtension('WEBGL_lose_context');
        if (lose) lose.loseContext();
        mount.remove();
    }, LIFE_MS + 400);
})();

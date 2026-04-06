function e(e,t,i,r){var o,s=arguments.length,a=s<3?t:null===r?r=Object.getOwnPropertyDescriptor(t,i):r;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)a=Reflect.decorate(e,t,i,r);else for(var n=e.length-1;n>=0;n--)(o=e[n])&&(a=(s<3?o(a):s>3?o(t,i,a):o(t,i))||a);return s>3&&a&&Object.defineProperty(t,i,a),a}"function"==typeof SuppressedError&&SuppressedError;const t=globalThis,i=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,r=Symbol(),o=new WeakMap;let s=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==r)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o;const t=this.t;if(i&&void 0===e){const i=void 0!==t&&1===t.length;i&&(e=o.get(t)),void 0===e&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&o.set(t,e))}return e}toString(){return this.cssText}};const a=(e,...t)=>{const i=1===e.length?e[0]:t.reduce((t,i,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if("number"==typeof e)return e;throw Error("Value passed to 'css' function must be a 'css' function result: "+e+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+e[r+1],e[0]);return new s(i,e,r)},n=i?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t="";for(const i of e.cssRules)t+=i.cssText;return(e=>new s("string"==typeof e?e:e+"",void 0,r))(t)})(e):e,{is:l,defineProperty:d,getOwnPropertyDescriptor:c,getOwnPropertyNames:p,getOwnPropertySymbols:h,getPrototypeOf:u}=Object,f=globalThis,v=f.trustedTypes,g=v?v.emptyScript:"",b=f.reactiveElementPolyfillSupport,m=(e,t)=>e,y={toAttribute(e,t){switch(t){case Boolean:e=e?g:null;break;case Object:case Array:e=null==e?e:JSON.stringify(e)}return e},fromAttribute(e,t){let i=e;switch(t){case Boolean:i=null!==e;break;case Number:i=null===e?null:Number(e);break;case Object:case Array:try{i=JSON.parse(e)}catch(e){i=null}}return i}},x=(e,t)=>!l(e,t),$={attribute:!0,type:String,converter:y,reflect:!1,useDefault:!1,hasChanged:x};Symbol.metadata??=Symbol("metadata"),f.litPropertyMetadata??=new WeakMap;let _=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=$){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){const i=Symbol(),r=this.getPropertyDescriptor(e,i,t);void 0!==r&&d(this.prototype,e,r)}}static getPropertyDescriptor(e,t,i){const{get:r,set:o}=c(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){const s=r?.call(this);o?.call(this,t),this.requestUpdate(e,s,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??$}static _$Ei(){if(this.hasOwnProperty(m("elementProperties")))return;const e=u(this);e.finalize(),void 0!==e.l&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(m("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(m("properties"))){const e=this.properties,t=[...p(e),...h(e)];for(const i of t)this.createProperty(i,e[i])}const e=this[Symbol.metadata];if(null!==e){const t=litPropertyMetadata.get(e);if(void 0!==t)for(const[e,i]of t)this.elementProperties.set(e,i)}this._$Eh=new Map;for(const[e,t]of this.elementProperties){const i=this._$Eu(e,t);void 0!==i&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){const t=[];if(Array.isArray(e)){const i=new Set(e.flat(1/0).reverse());for(const e of i)t.unshift(n(e))}else void 0!==e&&t.push(n(e));return t}static _$Eu(e,t){const i=t.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof e?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),void 0!==this.renderRoot&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){const e=new Map,t=this.constructor.elementProperties;for(const i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){const e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((e,r)=>{if(i)e.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(const i of r){const r=document.createElement("style"),o=t.litNonce;void 0!==o&&r.setAttribute("nonce",o),r.textContent=i.cssText,e.appendChild(r)}})(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){const i=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,i);if(void 0!==r&&!0===i.reflect){const o=(void 0!==i.converter?.toAttribute?i.converter:y).toAttribute(t,i.type);this._$Em=e,null==o?this.removeAttribute(r):this.setAttribute(r,o),this._$Em=null}}_$AK(e,t){const i=this.constructor,r=i._$Eh.get(e);if(void 0!==r&&this._$Em!==r){const e=i.getPropertyOptions(r),o="function"==typeof e.converter?{fromAttribute:e.converter}:void 0!==e.converter?.fromAttribute?e.converter:y;this._$Em=r;const s=o.fromAttribute(t,e.type);this[r]=s??this._$Ej?.get(r)??s,this._$Em=null}}requestUpdate(e,t,i,r=!1,o){if(void 0!==e){const s=this.constructor;if(!1===r&&(o=this[e]),i??=s.getPropertyOptions(e),!((i.hasChanged??x)(o,t)||i.useDefault&&i.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(s._$Eu(e,i))))return;this.C(e,t,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:r,wrapped:o},s){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,s??t??this[e]),!0!==o||void 0!==s)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}const e=this.scheduleUpdate();return null!=e&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}const e=this.constructor.elementProperties;if(e.size>0)for(const[t,i]of e){const{wrapped:e}=i,r=this[t];!0!==e||this._$AL.has(t)||void 0===r||this.C(t,void 0,i,r)}}let e=!1;const t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[m("elementProperties")]=new Map,_[m("finalized")]=new Map,b?.({ReactiveElement:_}),(f.reactiveElementVersions??=[]).push("2.1.2");const w=globalThis,A=e=>e,k=w.trustedTypes,P=k?k.createPolicy("lit-html",{createHTML:e=>e}):void 0,C="$lit$",E=`lit$${Math.random().toFixed(9).slice(2)}$`,S="?"+E,O=`<${S}>`,j=document,T=()=>j.createComment(""),U=e=>null===e||"object"!=typeof e&&"function"!=typeof e,I=Array.isArray,z="[ \t\n\f\r]",D=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,N=/-->/g,R=/>/g,H=RegExp(`>|${z}(?:([^\\s"'>=/]+)(${z}*=${z}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),M=/'/g,L=/"/g,B=/^(?:script|style|textarea|title)$/i,F=(e=>(t,...i)=>({_$litType$:e,strings:t,values:i}))(1),q=Symbol.for("lit-noChange"),V=Symbol.for("lit-nothing"),W=new WeakMap,G=j.createTreeWalker(j,129);function Y(e,t){if(!I(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==P?P.createHTML(t):t}class J{constructor({strings:e,_$litType$:t},i){let r;this.parts=[];let o=0,s=0;const a=e.length-1,n=this.parts,[l,d]=((e,t)=>{const i=e.length-1,r=[];let o,s=2===t?"<svg>":3===t?"<math>":"",a=D;for(let t=0;t<i;t++){const i=e[t];let n,l,d=-1,c=0;for(;c<i.length&&(a.lastIndex=c,l=a.exec(i),null!==l);)c=a.lastIndex,a===D?"!--"===l[1]?a=N:void 0!==l[1]?a=R:void 0!==l[2]?(B.test(l[2])&&(o=RegExp("</"+l[2],"g")),a=H):void 0!==l[3]&&(a=H):a===H?">"===l[0]?(a=o??D,d=-1):void 0===l[1]?d=-2:(d=a.lastIndex-l[2].length,n=l[1],a=void 0===l[3]?H:'"'===l[3]?L:M):a===L||a===M?a=H:a===N||a===R?a=D:(a=H,o=void 0);const p=a===H&&e[t+1].startsWith("/>")?" ":"";s+=a===D?i+O:d>=0?(r.push(n),i.slice(0,d)+C+i.slice(d)+E+p):i+E+(-2===d?t:p)}return[Y(e,s+(e[i]||"<?>")+(2===t?"</svg>":3===t?"</math>":"")),r]})(e,t);if(this.el=J.createElement(l,i),G.currentNode=this.el.content,2===t||3===t){const e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;null!==(r=G.nextNode())&&n.length<a;){if(1===r.nodeType){if(r.hasAttributes())for(const e of r.getAttributeNames())if(e.endsWith(C)){const t=d[s++],i=r.getAttribute(e).split(E),a=/([.?@])?(.*)/.exec(t);n.push({type:1,index:o,name:a[2],strings:i,ctor:"."===a[1]?ee:"?"===a[1]?te:"@"===a[1]?ie:X}),r.removeAttribute(e)}else e.startsWith(E)&&(n.push({type:6,index:o}),r.removeAttribute(e));if(B.test(r.tagName)){const e=r.textContent.split(E),t=e.length-1;if(t>0){r.textContent=k?k.emptyScript:"";for(let i=0;i<t;i++)r.append(e[i],T()),G.nextNode(),n.push({type:2,index:++o});r.append(e[t],T())}}}else if(8===r.nodeType)if(r.data===S)n.push({type:2,index:o});else{let e=-1;for(;-1!==(e=r.data.indexOf(E,e+1));)n.push({type:7,index:o}),e+=E.length-1}o++}}static createElement(e,t){const i=j.createElement("template");return i.innerHTML=e,i}}function K(e,t,i=e,r){if(t===q)return t;let o=void 0!==r?i._$Co?.[r]:i._$Cl;const s=U(t)?void 0:t._$litDirective$;return o?.constructor!==s&&(o?._$AO?.(!1),void 0===s?o=void 0:(o=new s(e),o._$AT(e,i,r)),void 0!==r?(i._$Co??=[])[r]=o:i._$Cl=o),void 0!==o&&(t=K(e,o._$AS(e,t.values),o,r)),t}class Z{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){const{el:{content:t},parts:i}=this._$AD,r=(e?.creationScope??j).importNode(t,!0);G.currentNode=r;let o=G.nextNode(),s=0,a=0,n=i[0];for(;void 0!==n;){if(s===n.index){let t;2===n.type?t=new Q(o,o.nextSibling,this,e):1===n.type?t=new n.ctor(o,n.name,n.strings,this,e):6===n.type&&(t=new re(o,this,e)),this._$AV.push(t),n=i[++a]}s!==n?.index&&(o=G.nextNode(),s++)}return G.currentNode=j,r}p(e){let t=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}}class Q{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,r){this.type=2,this._$AH=V,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode;const t=this._$AM;return void 0!==t&&11===e?.nodeType&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=K(this,e,t),U(e)?e===V||null==e||""===e?(this._$AH!==V&&this._$AR(),this._$AH=V):e!==this._$AH&&e!==q&&this._(e):void 0!==e._$litType$?this.$(e):void 0!==e.nodeType?this.T(e):(e=>I(e)||"function"==typeof e?.[Symbol.iterator])(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==V&&U(this._$AH)?this._$AA.nextSibling.data=e:this.T(j.createTextNode(e)),this._$AH=e}$(e){const{values:t,_$litType$:i}=e,r="number"==typeof i?this._$AC(e):(void 0===i.el&&(i.el=J.createElement(Y(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(t);else{const e=new Z(r,this),i=e.u(this.options);e.p(t),this.T(i),this._$AH=e}}_$AC(e){let t=W.get(e.strings);return void 0===t&&W.set(e.strings,t=new J(e)),t}k(e){I(this._$AH)||(this._$AH=[],this._$AR());const t=this._$AH;let i,r=0;for(const o of e)r===t.length?t.push(i=new Q(this.O(T()),this.O(T()),this,this.options)):i=t[r],i._$AI(o),r++;r<t.length&&(this._$AR(i&&i._$AB.nextSibling,r),t.length=r)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){const t=A(e).nextSibling;A(e).remove(),e=t}}setConnected(e){void 0===this._$AM&&(this._$Cv=e,this._$AP?.(e))}}class X{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,r,o){this.type=1,this._$AH=V,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=o,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=V}_$AI(e,t=this,i,r){const o=this.strings;let s=!1;if(void 0===o)e=K(this,e,t,0),s=!U(e)||e!==this._$AH&&e!==q,s&&(this._$AH=e);else{const r=e;let a,n;for(e=o[0],a=0;a<o.length-1;a++)n=K(this,r[i+a],t,a),n===q&&(n=this._$AH[a]),s||=!U(n)||n!==this._$AH[a],n===V?e=V:e!==V&&(e+=(n??"")+o[a+1]),this._$AH[a]=n}s&&!r&&this.j(e)}j(e){e===V?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}}class ee extends X{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===V?void 0:e}}class te extends X{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==V)}}class ie extends X{constructor(e,t,i,r,o){super(e,t,i,r,o),this.type=5}_$AI(e,t=this){if((e=K(this,e,t,0)??V)===q)return;const i=this._$AH,r=e===V&&i!==V||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,o=e!==V&&(i===V||r);r&&this.element.removeEventListener(this.name,this,i),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}}class re{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){K(this,e)}}const oe={I:Q},se=w.litHtmlPolyfillSupport;se?.(J,Q),(w.litHtmlVersions??=[]).push("3.3.2");const ae=globalThis;let ne=class extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){const t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=((e,t,i)=>{const r=i?.renderBefore??t;let o=r._$litPart$;if(void 0===o){const e=i?.renderBefore??null;r._$litPart$=o=new Q(t.insertBefore(T(),e),e,void 0,i??{})}return o._$AI(e),o})(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return q}};ne._$litElement$=!0,ne.finalized=!0,ae.litElementHydrateSupport?.({LitElement:ne});const le=ae.litElementPolyfillSupport;le?.({LitElement:ne}),(ae.litElementVersions??=[]).push("4.2.2");const de=e=>(t,i)=>{void 0!==i?i.addInitializer(()=>{customElements.define(e,t)}):customElements.define(e,t)},ce={attribute:!0,type:String,converter:y,reflect:!1,hasChanged:x},pe=(e=ce,t,i)=>{const{kind:r,metadata:o}=i;let s=globalThis.litPropertyMetadata.get(o);if(void 0===s&&globalThis.litPropertyMetadata.set(o,s=new Map),"setter"===r&&((e=Object.create(e)).wrapped=!0),s.set(i.name,e),"accessor"===r){const{name:r}=i;return{set(i){const o=t.get.call(this);t.set.call(this,i),this.requestUpdate(r,o,e,!0,i)},init(t){return void 0!==t&&this.C(r,void 0,e,t),t}}}if("setter"===r){const{name:r}=i;return function(i){const o=this[r];t.call(this,i),this.requestUpdate(r,o,e,!0,i)}}throw Error("Unsupported decorator location: "+r)};function he(e){return(t,i)=>"object"==typeof i?pe(e,t,i):((e,t,i)=>{const r=t.hasOwnProperty(i);return t.constructor.createProperty(i,e),r?Object.getOwnPropertyDescriptor(t,i):void 0})(e,t,i)}function ue(e){return he({...e,state:!0,attribute:!1})}let fe=class extends ne{constructor(){super(),Object.defineProperty(this,"config",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"hasError",{enumerable:!0,configurable:!0,writable:!0,value:!1}),Object.defineProperty(this,"error",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"errorCount",{enumerable:!0,configurable:!0,writable:!0,value:0}),Object.defineProperty(this,"childRender",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"handleUnhandledRejection",{enumerable:!0,configurable:!0,writable:!0,value:e=>{this.contains(e.target)&&(this.handleError(new Error(`Promise rejection: ${e.reason}`)),e.preventDefault())}}),Object.defineProperty(this,"handleError",{enumerable:!0,configurable:!0,writable:!0,value:e=>{const t=e instanceof ErrorEvent?e.error:e;this.errorCount++,t&&(this.hasError=!0,this.error=t,console.error(`[Isolator Error Boundary] Component crashed (attempt #${this.errorCount}):`,t.message,t.stack),this.config?.onError&&this.config.onError(t,()=>this.retry()))}}),Object.defineProperty(this,"retry",{enumerable:!0,configurable:!0,writable:!0,value:()=>{this.hasError=!1,this.error=void 0,this.requestUpdate()}}),this.addEventListener("error",e=>this.handleError(e),!0)}connectedCallback(){super.connectedCallback(),window.addEventListener("unhandledrejection",this.handleUnhandledRejection)}disconnectedCallback(){super.disconnectedCallback(),window.removeEventListener("unhandledrejection",this.handleUnhandledRejection)}setChildRender(e){this.childRender=e,this.requestUpdate()}render(){if(this.hasError)return this.renderErrorFallback();if(this.childRender)try{return this.childRender()}catch(e){return this.handleError(e instanceof Error?e:new Error(String(e))),this.renderErrorFallback()}return V}renderErrorFallback(){const e=this.config?.title||"Perimeter Control",t=this.config?.fallbackMessage||"Failed to load integration",i=!1!==this.config?.showDetails;return F`
      <ha-card>
        <div class="card-content" style="padding: 16px;">
          <div style="
            border: 1px solid #ff5722;
            border-radius: 4px;
            padding: 12px;
            background-color: #ffebee;
            color: #c62828;
          ">
            <div style="font-weight: bold; margin-bottom: 8px;">⚠️ ${e}</div>
            <div style="margin-bottom: 8px;">${t}</div>
            
            ${i&&this.error?F`
                <details style="margin-top: 8px; font-size: 0.9em; color: #d32f2f;">
                  <summary style="cursor: pointer; user-select: none;">Error details</summary>
                  <pre style="
                    margin: 8px 0 0 0;
                    padding: 8px;
                    background: rgba(0,0,0,0.05);
                    border-radius: 2px;
                    overflow-x: auto;
                    font-size: 0.85em;
                  ">${this.error.message}
${this.error.stack||"No stack trace available"}</pre>
                </details>
              `:V}

            <div style="margin-top: 12px;">
              <button
                @click=${this.retry}
                style="
                  padding: 8px 16px;
                  background-color: #ff5722;
                  color: white;
                  border: none;
                  border-radius: 2px;
                  cursor: pointer;
                  font-weight: bold;
                "
              >
                🔄 Retry
              </button>
              <span style="margin-left: 12px; font-size: 0.9em;">
                Attempt ${this.errorCount}
                ${this.errorCount>3?" - Consider checking Home Assistant logs":""}
              </span>
            </div>

            <div style="margin-top: 12px; font-size: 0.85em; opacity: 0.7;">
              <strong>Troubleshooting steps:</strong>
              <ul style="margin: 4px 0; padding-left: 20px;">
                <li>Check your browser console for errors (F12 → Console tab)</li>
                <li>Verify Isolator Supervisor is running at the configured API URL</li>
                <li>Check your Home Assistant logs for related errors</li>
                <li>If problem persists, disable this card by removing it from your YAML configuration</li>
              </ul>
            </div>
          </div>
        </div>
      </ha-card>
    `}static getStyles(){return"\n      :host {\n        display: block;\n      }\n      \n      ha-card {\n        box-shadow: 0 2px 4px rgba(0,0,0,0.1);\n        border-radius: 4px;\n      }\n    "}};e([he({attribute:!1})],fe.prototype,"config",void 0),e([ue()],fe.prototype,"hasError",void 0),e([ue()],fe.prototype,"error",void 0),e([ue()],fe.prototype,"errorCount",void 0),fe=e([de("perimeter-control-error-boundary")],fe);let ve=class extends fe{};ve=e([de("isolator-error-boundary")],ve);let ge=class extends ne{constructor(){super(...arguments),Object.defineProperty(this,"config",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"state",{enumerable:!0,configurable:!0,writable:!0,value:"loading"}),Object.defineProperty(this,"isApiHealthy",{enumerable:!0,configurable:!0,writable:!0,value:!1}),Object.defineProperty(this,"retryCount",{enumerable:!0,configurable:!0,writable:!0,value:0}),Object.defineProperty(this,"lastError",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"loadingTimeout",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"healthCheckAbort",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"retry",{enumerable:!0,configurable:!0,writable:!0,value:()=>{this.retryCount=0,this.performHealthCheck()}})}connectedCallback(){super.connectedCallback(),this.performHealthCheck()}disconnectedCallback(){super.disconnectedCallback(),this.loadingTimeout&&clearTimeout(this.loadingTimeout),this.healthCheckAbort&&this.healthCheckAbort.abort()}async performHealthCheck(){if(!this.config)return this.state="error",void(this.lastError="No configuration provided");const e=this.config.timeout||1e4,t=this.config.healthCheckPath||"/api/v1/services",i=this.config.apiUrl.replace(/\/$/,"");this.state="loading",this.healthCheckAbort=new AbortController;const r=setTimeout(()=>{this.healthCheckAbort?.abort(),this.state="timeout",this.lastError=`API did not respond within ${e}ms`,console.warn(`[Isolator Safe Loader] Health check timeout: ${i}`)},e);try{const e=await fetch(`${i}${t}`,{method:"GET",signal:this.healthCheckAbort.signal,headers:{Accept:"application/json"}});if(clearTimeout(r),!e.ok)throw new Error(`API returned ${e.status}: ${e.statusText}`);this.isApiHealthy=!0,this.state="ready",this.retryCount=0,console.log("[Isolator Safe Loader] API health check passed:",i)}catch(e){clearTimeout(r),e instanceof TypeError&&e.message.includes("Failed to fetch")?(this.state="offline",this.lastError="Cannot reach Isolator Supervisor API (network error or CORS issue)"):e instanceof DOMException&&"AbortError"===e.name||(this.state="error",this.lastError=e instanceof Error?e.message:String(e)),console.warn("[Isolator Safe Loader] Health check failed:",this.lastError);const t=this.config.maxRetries||3;if(this.retryCount<t){const e=this.config.backoffMultiplier||1.5,i=Math.min(1e3*Math.pow(e,this.retryCount),3e4);this.retryCount++,console.log(`[Isolator Safe Loader] Retrying in ${i}ms (attempt ${this.retryCount}/${t})`),this.loadingTimeout=setTimeout(()=>{this.isConnected&&this.performHealthCheck()},i)}}}render(){switch(this.state){case"ready":return F`<slot></slot>`;case"loading":return this.renderLoading();case"timeout":return this.renderTimeout();case"offline":return this.renderOffline();default:return this.renderError()}}renderLoading(){return F`
      <ha-card>
        <div class="card-content" style="padding: 16px; text-align: center;">
          <div style="font-size: 14px; color: #666;">
            ⏳ Loading Isolator Service Access...
          </div>
          <div style="
            margin-top: 8px;
            width: 24px;
            height: 24px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #ff5722;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: auto;
            margin-right: auto;
          "></div>
          <div style="font-size: 12px; color: #999; margin-top: 8px;">
            Checking Isolator Supervisor API...
          </div>
          <style>
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          </style>
        </div>
      </ha-card>
    `}renderTimeout(){return F`
      <ha-card>
        <div class="card-content" style="padding: 16px;">
          <div style="
            border: 1px solid #ff9800;
            border-radius: 4px;
            padding: 12px;
            background-color: #fff3e0;
            color: #e65100;
          ">
            <div style="font-weight: bold; margin-bottom: 8px;">⏱️ Connection Timeout</div>
            <div style="margin-bottom: 8px;">
              Isolator Supervisor is not responding (timeout after ${this.config?.timeout||1e4}ms).
            </div>

            <div style="margin-top: 8px; font-size: 0.9em;">
              <strong>This could mean:</strong>
              <ul style="margin: 4px 0; padding-left: 20px;">
                <li>Isolator Supervisor is not running</li>
                <li>API URL is incorrect: <code style="background: rgba(0,0,0,0.1); padding: 2px 4px;">${this.config?.apiUrl}</code></li>
                <li>Network connectivity issue</li>
                <li>Supervisor is overloaded</li>
              </ul>
            </div>

            <div style="margin-top: 12px;">
              <button
                @click=${this.retry}
                style="
                  padding: 8px 16px;
                  background-color: #ff9800;
                  color: white;
                  border: none;
                  border-radius: 2px;
                  cursor: pointer;
                  font-weight: bold;
                "
              >
                🔄 Retry Now
              </button>
              <span style="margin-left: 12px; font-size: 0.9em;">
                ${this.retryCount>0?"Will auto-retry...":""}
              </span>
            </div>

            <div style="margin-top: 12px; padding: 8px; background: rgba(0,0,0,0.05); border-radius: 2px; font-size: 0.85em;">
              <strong>Your Home Assistant is still working:</strong> This loading card will not affect other integrations or automations.
            </div>
          </div>
        </div>
      </ha-card>
    `}renderOffline(){return F`
      <ha-card>
        <div class="card-content" style="padding: 16px;">
          <div style="
            border: 1px solid #f44336;
            border-radius: 4px;
            padding: 12px;
            background-color: #ffebee;
            color: #c62828;
          ">
            <div style="font-weight: bold; margin-bottom: 8px;">🔌 API Offline</div>
            <div style="margin-bottom: 8px;">
              Cannot reach Isolator Supervisor API at <code style="background: rgba(0,0,0,0.1); padding: 2px 4px; word-break: break-all;">${this.config?.apiUrl}</code>
            </div>

            <div style="margin-top: 8px; font-size: 0.9em;">
              <strong>Network error or CORS issue detected.</strong>
              <ul style="margin: 4px 0; padding-left: 20px;">
                <li>Is Isolator Supervisor running on the target device?</li>
                <li>Is the network accessible from Home Assistant?</li>
                <li>Check firewall rules and network isolation</li>
                <li>Verify API URL is correct (HTTP/HTTPS, IP, port)</li>
              </ul>
            </div>

            <div style="
              margin-top: 12px;
              padding: 8px;
              background: #e3f2fd;
              border-radius: 2px;
              font-size: 0.85em;
              color: #1565c0;
            ">
              <strong>Check Home Assistant Logs:</strong>
              <div>Settings → Developer Tools → Logs (search for "Isolator")</div>
            </div>

            <div style="margin-top: 12px;">
              <button
                @click=${this.retry}
                style="
                  padding: 8px 16px;
                  background-color: #f44336;
                  color: white;
                  border: none;
                  border-radius: 2px;
                  cursor: pointer;
                  font-weight: bold;
                "
              >
                🔄 Retry
              </button>
              <span style="margin-left: 12px; font-size: 0.9em;">
                Attempt ${this.retryCount}
              </span>
            </div>

            <div style="margin-top: 12px; padding: 8px; background: rgba(0,0,0,0.05); border-radius: 2px; font-size: 0.85em;">
              ✓ <strong>Your Home Assistant is unaffected:</strong> This card-level failure will not impact other automations, scenes, or integrations.
            </div>
          </div>
        </div>
      </ha-card>
    `}renderError(){return F`
      <ha-card>
        <div class="card-content" style="padding: 16px;">
          <div style="
            border: 1px solid #f44336;
            border-radius: 4px;
            padding: 12px;
            background-color: #ffebee;
            color: #c62828;
          ">
            <div style="font-weight: bold; margin-bottom: 8px;">❌ Failed to Load</div>
            <div style="margin-bottom: 8px;">${this.lastError||"Unknown error"}</div>

            <div style="margin-top: 8px; font-size: 0.9em;">
              <strong>If this persists:</strong>
              <ul style="margin: 4px 0; padding-left: 20px;">
                <li>Check browser console (F12 → Console)</li>
                <li>Verify Isolator Supervisor version matches this integration</li>
                <li>Try removing and re-adding the card</li>
                <li>Disable the card temporarily by removing from YAML</li>
              </ul>
            </div>

            <div style="margin-top: 12px;">
              <button
                @click=${this.retry}
                style="
                  padding: 8px 16px;
                  background-color: #f44336;
                  color: white;
                  border: none;
                  border-radius: 2px;
                  cursor: pointer;
                  font-weight: bold;
                "
              >
                🔄 Retry
              </button>
            </div>

            <div style="margin-top: 12px; padding: 8px; background: rgba(0,0,0,0.05); border-radius: 2px; font-size: 0.85em;">
              ✓ <strong>Home Assistant is protected:</strong> This error is isolated to this card and won't affect your other systems.
            </div>
          </div>
        </div>
      </ha-card>
    `}};e([he({attribute:!1})],ge.prototype,"config",void 0),e([ue()],ge.prototype,"state",void 0),e([ue()],ge.prototype,"isApiHealthy",void 0),e([ue()],ge.prototype,"retryCount",void 0),e([ue()],ge.prototype,"lastError",void 0),ge=e([de("perimeter-control-safe-loader")],ge);let be=class extends ge{};be=e([de("isolator-safe-loader")],be);let me=class extends ne{constructor(){super(...arguments),Object.defineProperty(this,"apiBaseUrl",{enumerable:!0,configurable:!0,writable:!0,value:"http://localhost:8080"}),Object.defineProperty(this,"serviceId",{enumerable:!0,configurable:!0,writable:!0,value:""}),Object.defineProperty(this,"service",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"accessProfile",{enumerable:!0,configurable:!0,writable:!0,value:null}),Object.defineProperty(this,"loading",{enumerable:!0,configurable:!0,writable:!0,value:!0}),Object.defineProperty(this,"saving",{enumerable:!0,configurable:!0,writable:!0,value:!1}),Object.defineProperty(this,"error",{enumerable:!0,configurable:!0,writable:!0,value:null}),Object.defineProperty(this,"successMessage",{enumerable:!0,configurable:!0,writable:!0,value:null})}async connectedCallback(){super.connectedCallback(),this.serviceId&&await this.loadAccessProfile()}async loadAccessProfile(){this.loading=!0,this.error=null;try{const e=`${this.apiBaseUrl}/api/v1/services/${this.serviceId}/access`,t=await fetch(e);if(!t.ok)throw new Error(`API returned ${t.status}: ${t.statusText}`);const i=await t.json();this.accessProfile=i.access_profile}catch(e){this.error=e instanceof Error?e.message:"Failed to load access profile"}finally{this.loading=!1}}async saveAccessProfile(){if(this.accessProfile){this.saving=!0,this.error=null,this.successMessage=null;try{const e=`${this.apiBaseUrl}/api/v1/services/${this.serviceId}/access`,t=await fetch(e,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(this.accessProfile)});if(!t.ok){const e=await t.text();throw new Error(`API returned ${t.status}: ${e||t.statusText}`)}this.successMessage="Access profile updated successfully!",setTimeout(()=>{this.successMessage=null},3e3)}catch(e){this.error=e instanceof Error?e.message:"Failed to save access profile"}finally{this.saving=!1}}}updateField(e,t){this.accessProfile&&(this.accessProfile={...this.accessProfile,[e]:t})}addOrigin(e){if(!this.accessProfile||!e.trim())return;const t=[...this.accessProfile.allowed_origins||[]];t.includes(e)||(t.push(e),this.updateField("allowed_origins",t))}removeOrigin(e){if(!this.accessProfile)return;const t=this.accessProfile.allowed_origins.filter((t,i)=>i!==e);this.updateField("allowed_origins",t)}render(){return this.loading?F`
        <div class="container">
          <div class="info-box loading">
            <span class="spinner"></span> Loading access profile...
          </div>
        </div>
      `:this.error?F`
        <div class="container">
          <div class="info-box error">${this.error}</div>
          <div class="actions">
            <button class="btn-cancel" @click=${()=>this.loadAccessProfile()}>
              Retry
            </button>
          </div>
        </div>
      `:this.accessProfile?F`
      <div class="container">
        <div class="header">
          <h3>${this.service?.name||this.serviceId}</h3>
          <span class="status-badge ready">Ready</span>
        </div>

        ${this.successMessage?F` <div class="info-box success">${this.successMessage}</div> `:""}
        ${this.error?F` <div class="info-box error">${this.error}</div> `:""}

        <div class="form-grid">
          <!-- Mode -->
          <div class="form-group">
            <label>Access Mode</label>
            <select
              .value=${this.accessProfile.mode}
              @change=${e=>this.updateField("mode",e.target.value)}
              ?disabled=${this.saving}
            >
              <option value="isolated">Isolated (No upstream)</option>
              <option value="upstream">Upstream (Forward to origin)</option>
              <option value="passthrough">Passthrough (Direct proxy)</option>
            </select>
            <div class="field-hint">How this service connects to clients and upstreams</div>
          </div>

          <!-- Port -->
          <div class="form-group">
            <label>Port</label>
            <input
              type="number"
              .value=${this.accessProfile.port}
              @change=${e=>this.updateField("port",parseInt(e.target.value))}
              ?disabled=${this.saving}
              min="1"
              max="65535"
            />
            <div class="field-hint">Service listen port</div>
          </div>

          <!-- Bind Address -->
          <div class="form-group">
            <label>Bind Address</label>
            <input
              type="text"
              .value=${this.accessProfile.bind_address}
              @change=${e=>this.updateField("bind_address",e.target.value)}
              ?disabled=${this.saving}
              placeholder="0.0.0.0 or ::1"
            />
            <div class="field-hint">Leave empty for all interfaces</div>
          </div>

          <!-- TLS Mode -->
          <div class="form-group">
            <label>TLS Mode</label>
            <select
              .value=${this.accessProfile.tls_mode}
              @change=${e=>this.updateField("tls_mode",e.target.value)}
              ?disabled=${this.saving}
            >
              <option value="disabled">Disabled (HTTP only)</option>
              <option value="self_signed">Self-signed Certificate</option>
              <option value="external">External CA</option>
              <option value="custom">Custom Certificate</option>
            </select>
            <div class="field-hint">Transport layer security</div>
          </div>

          <!-- Auth Mode -->
          <div class="form-group">
            <label>Authentication</label>
            <select
              .value=${this.accessProfile.auth_mode}
              @change=${e=>this.updateField("auth_mode",e.target.value)}
              ?disabled=${this.saving}
            >
              <option value="none">None (Public)</option>
              <option value="token">Token-based</option>
              <option value="oauth2">OAuth 2.0</option>
              <option value="mTLS">mTLS (Certificate)</option>
            </select>
            <div class="field-hint">Service-level authentication</div>
          </div>

          <!-- Exposure Scope -->
          <div class="form-group">
            <label>Exposure Scope</label>
            <select
              .value=${this.accessProfile.exposure_scope}
              @change=${e=>this.updateField("exposure_scope",e.target.value)}
              ?disabled=${this.saving}
            >
              <option value="local_only">Localhost Only</option>
              <option value="lan_only">LAN Only</option>
              <option value="wan_limited">WAN (Rate-limited)</option>
              <option value="wan_full">WAN (Full)</option>
            </select>
            <div class="field-hint">Geographic scope of allowed clients</div>
          </div>

          <!-- Allowed Origins -->
          <div class="form-group full">
            <label>Allowed CORS Origins</label>
            <textarea
              ?disabled=${this.saving}
              placeholder="https://example.com (one per line)"
              @blur=${e=>{const t=e.target.value.trim();t&&(this.addOrigin(t),e.target.value="")}}
              rows="2"
            ></textarea>
            ${this.accessProfile.allowed_origins.length>0?F`
                  <div class="origins-list">
                    ${this.accessProfile.allowed_origins.map((e,t)=>F`
                      <div class="origin-item">
                        <span>${e}</span>
                        <button
                          type="button"
                          @click=${()=>this.removeOrigin(t)}
                          ?disabled=${this.saving}
                        >
                          ✕
                        </button>
                      </div>
                    `)}
                  </div>
                `:""}
          </div>
        </div>

        <div class="actions">
          <button
            class="btn-cancel"
            @click=${()=>this.loadAccessProfile()}
            ?disabled=${this.saving}
          >
            Cancel
          </button>
          <button
            class="btn-save"
            @click=${()=>this.saveAccessProfile()}
            ?disabled=${this.saving}
          >
            ${this.saving?F`<span class="spinner"></span> Saving...`:"Save Changes"}
          </button>
        </div>
      </div>
    `:F`<div class="container">No access profile available</div>`}};Object.defineProperty(me,"styles",{enumerable:!0,configurable:!0,writable:!0,value:a`
    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
        Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
      --primary-color: #03a9f4;
      --error-color: #f44336;
      --success-color: #4caf50;
    }

    .container {
      padding: 16px;
      background: linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%);
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
    }

    .header h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: #212121;
    }

    .status-badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
    }

    .status-badge.loading {
      background: #e3f2fd;
      color: #1976d2;
    }

    .status-badge.ready {
      background: #e8f5e9;
      color: #388e3c;
    }

    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 16px;
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .form-group.full {
      grid-column: 1 / -1;
    }

    label {
      font-size: 12px;
      font-weight: 600;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    input,
    select,
    textarea {
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-family: inherit;
      font-size: 13px;
      background: white;
      color: #212121;
      transition: border-color 0.2s, box-shadow 0.2s;
    }

    input:focus,
    select:focus,
    textarea:focus {
      outline: none;
      border-color: var(--primary-color);
      box-shadow: 0 0 0 2px rgba(3, 169, 244, 0.1);
    }

    input:disabled,
    select:disabled {
      background: #f5f5f5;
      color: #999;
      cursor: not-allowed;
    }

    .field-hint {
      font-size: 11px;
      color: #999;
      margin-top: 2px;
    }

    .info-box {
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 12px;
      margin-bottom: 12px;
    }

    .info-box.error {
      background: #ffebee;
      color: #c62828;
      border-left: 3px solid var(--error-color);
    }

    .info-box.success {
      background: #e8f5e9;
      color: #2e7d32;
      border-left: 3px solid var(--success-color);
    }

    .info-box.loading {
      background: #e3f2fd;
      color: #1565c0;
      border-left: 3px solid var(--primary-color);
    }

    .actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }

    button {
      padding: 8px 16px;
      border: none;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .btn-save {
      background: var(--primary-color);
      color: white;
    }

    .btn-save:hover:not(:disabled) {
      background: #0288d1;
      box-shadow: 0 2px 8px rgba(3, 169, 244, 0.3);
    }

    .btn-cancel {
      background: #e0e0e0;
      color: #212121;
    }

    .btn-cancel:hover:not(:disabled) {
      background: #d0d0d0;
    }

    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .origins-list {
      padding: 8px;
      background: white;
      border: 1px solid #ddd;
      border-radius: 4px;
      margin-top: 4px;
      font-size: 12px;
      max-height: 120px;
      overflow-y: auto;
    }

    .origin-item {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 4px;
      margin-bottom: 2px;
    }

    .origin-item button {
      padding: 2px 6px;
      font-size: 11px;
      background: #ffcdd2;
      color: #c62828;
    }

    .origin-item button:hover {
      background: #ef5350;
      color: white;
    }

    .spinner {
      display: inline-block;
      width: 14px;
      height: 14px;
      border: 2px solid #e0e0e0;
      border-top-color: var(--primary-color);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
  `}),e([he({type:String})],me.prototype,"apiBaseUrl",void 0),e([he({type:String})],me.prototype,"serviceId",void 0),e([he({type:Object})],me.prototype,"service",void 0),e([ue()],me.prototype,"accessProfile",void 0),e([ue()],me.prototype,"loading",void 0),e([ue()],me.prototype,"saving",void 0),e([ue()],me.prototype,"error",void 0),e([ue()],me.prototype,"successMessage",void 0),me=e([de("perimeter-control-service-access-editor")],me);let ye=class extends me{};ye=e([de("isolator-service-access-editor")],ye);const xe=2;let $e=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,i){this._$Ct=e,this._$AM=t,this._$Ci=i}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}};const{I:_e}=oe,we=e=>e,Ae=()=>document.createComment(""),ke=(e,t,i)=>{const r=e._$AA.parentNode,o=void 0===t?e._$AB:t._$AA;if(void 0===i){const t=r.insertBefore(Ae(),o),s=r.insertBefore(Ae(),o);i=new _e(t,s,e,e.options)}else{const t=i._$AB.nextSibling,s=i._$AM,a=s!==e;if(a){let t;i._$AQ?.(e),i._$AM=e,void 0!==i._$AP&&(t=e._$AU)!==s._$AU&&i._$AP(t)}if(t!==o||a){let e=i._$AA;for(;e!==t;){const t=we(e).nextSibling;we(r).insertBefore(e,o),e=t}}}return i},Pe=(e,t,i=e)=>(e._$AI(t,i),e),Ce={},Ee=(e,t=Ce)=>e._$AH=t,Se=e=>{e._$AR(),e._$AA.remove()},Oe=(e,t,i)=>{const r=new Map;for(let o=t;o<=i;o++)r.set(e[o],o);return r},je=(e=>(...t)=>({_$litDirective$:e,values:t}))(class extends $e{constructor(e){if(super(e),e.type!==xe)throw Error("repeat() can only be used in text expressions")}dt(e,t,i){let r;void 0===i?i=t:void 0!==t&&(r=t);const o=[],s=[];let a=0;for(const t of e)o[a]=r?r(t,a):a,s[a]=i(t,a),a++;return{values:s,keys:o}}render(e,t,i){return this.dt(e,t,i).values}update(e,[t,i,r]){const o=(e=>e._$AH)(e),{values:s,keys:a}=this.dt(t,i,r);if(!Array.isArray(o))return this.ut=a,s;const n=this.ut??=[],l=[];let d,c,p=0,h=o.length-1,u=0,f=s.length-1;for(;p<=h&&u<=f;)if(null===o[p])p++;else if(null===o[h])h--;else if(n[p]===a[u])l[u]=Pe(o[p],s[u]),p++,u++;else if(n[h]===a[f])l[f]=Pe(o[h],s[f]),h--,f--;else if(n[p]===a[f])l[f]=Pe(o[p],s[f]),ke(e,l[f+1],o[p]),p++,f--;else if(n[h]===a[u])l[u]=Pe(o[h],s[u]),ke(e,o[p],o[h]),h--,u++;else if(void 0===d&&(d=Oe(a,u,f),c=Oe(n,p,h)),d.has(n[p]))if(d.has(n[h])){const t=c.get(a[u]),i=void 0!==t?o[t]:null;if(null===i){const t=ke(e,o[p]);Pe(t,s[u]),l[u]=t}else l[u]=Pe(i,s[u]),ke(e,o[p],i),o[t]=null;u++}else Se(o[h]),h--;else Se(o[p]),p++;for(;u<=f;){const t=ke(e,l[f+1]);Pe(t,s[u]),l[u++]=t}for(;p<=h;){const e=o[p++];null!==e&&Se(e)}return this.ut=a,Ee(e,l),q}});let Te=class extends ne{constructor(){super(...arguments),Object.defineProperty(this,"nodes",{enumerable:!0,configurable:!0,writable:!0,value:[]}),Object.defineProperty(this,"autoRefresh",{enumerable:!0,configurable:!0,writable:!0,value:!0}),Object.defineProperty(this,"refreshInterval",{enumerable:!0,configurable:!0,writable:!0,value:3e4}),Object.defineProperty(this,"selectedNode",{enumerable:!0,configurable:!0,writable:!0,value:null}),Object.defineProperty(this,"selectedService",{enumerable:!0,configurable:!0,writable:!0,value:null}),Object.defineProperty(this,"loading",{enumerable:!0,configurable:!0,writable:!0,value:!1}),Object.defineProperty(this,"error",{enumerable:!0,configurable:!0,writable:!0,value:null}),Object.defineProperty(this,"refreshTimer",{enumerable:!0,configurable:!0,writable:!0,value:void 0})}connectedCallback(){super.connectedCallback(),this.autoRefresh&&this.startAutoRefresh()}disconnectedCallback(){super.disconnectedCallback(),this.stopAutoRefresh()}startAutoRefresh(){this.refreshTimer=window.setInterval(()=>{this.refreshAllNodes()},this.refreshInterval)}stopAutoRefresh(){this.refreshTimer&&clearInterval(this.refreshTimer)}async refreshAllNodes(){for(const e of this.nodes)await this.loadNodeFeatures(e),await this.loadNodeServices(e)}async loadNodeFeatures(e){try{e.status="connecting";const t=await fetch(`${e.url}/api/v1/node/features?timeout=10`);if(!t.ok)throw new Error(`HTTP ${t.status}`);const i=await t.json();e.features=i.node_features,e.status="online",e.lastUpdate=Date.now(),e.error=void 0}catch(t){e.status="offline",e.error=t instanceof Error?t.message:"Unknown error"}this.requestUpdate()}async loadNodeServices(e){try{const t=await fetch(`${e.url}/api/v1/services?timeout=5`);if(!t.ok)throw new Error(`HTTP ${t.status}`);const i=await t.json();e.services=i.services||[]}catch(t){e.services=[]}this.requestUpdate()}selectNode(e){this.selectedNode=e,this.selectedService=null}selectService(e){this.selectedService=e}render(){return F`
      <div class="container">
        <!-- Sidebar: Node List -->
        <div class="sidebar">
          <div class="sidebar-header">
            🔗 Isolator Fleet
            <div style="font-size: 11px; font-weight: normal; color: #999; margin-top: 4px;">
              ${this.nodes.length} node${1!==this.nodes.length?"s":""}
            </div>
          </div>
          <div class="node-list">
            ${0===this.nodes.length?F`<div class="placeholder" style="padding: 20px;"><div>No nodes configured</div></div>`:je(this.nodes,e=>e.url,e=>F`
                    <div
                      class="node-item ${this.selectedNode?.url===e.url?"selected":""}"
                      @click=${()=>this.selectNode(e)}
                    >
                      <div class="node-status ${e.status}"></div>
                      <div style="flex: 1; overflow: hidden;">
                        <div style="font-weight: 600; text-overflow: ellipsis; overflow: hidden;">
                          ${e.name}
                        </div>
                        <div style="font-size: 11px; color: #999; text-overflow: ellipsis; overflow: hidden;">
                          ${e.url}
                        </div>
                      </div>
                    </div>
                  `)}
          </div>
        </div>

        <!-- Main Content -->
        <div class="main">
          ${this.selectedNode?F`
                <div class="main-header">
                  <div>
                    <h2>${this.selectedNode.name}</h2>
                    <div style="font-size: 12px; color: #999; margin-top: 4px;">
                      Status: <strong>${this.selectedNode.status}</strong>
                      ${this.selectedNode.lastUpdate?` • Updated: ${new Date(this.selectedNode.lastUpdate).toLocaleTimeString()}`:""}
                    </div>
                  </div>
                  <button class="refresh-btn" @click=${()=>this.loadNodeFeatures(this.selectedNode)}>
                    ⟳ Refresh
                  </button>
                </div>

                ${this.selectedNode.error?F`<div class="error-box">${this.selectedNode.error}</div>`:""}

                <div class="tabs">
                  <button
                    class="tab ${this.selectedService?"":"active"}"
                    @click=${()=>this.selectService(null)}
                  >
                    Features
                  </button>
                  <button
                    class="tab ${this.selectedService?"active":""}"
                    @click=${()=>{}}
                  >
                    Services (${this.selectedNode.services?.length||0})
                  </button>
                </div>

                ${this.selectedService?this.renderServices(this.selectedNode):this.renderFeatures(this.selectedNode)}
              `:F`
                <div class="placeholder">
                  <div class="placeholder-icon">🛰️</div>
                  <div>Select a node to view details</div>
                </div>
              `}
        </div>
      </div>
    `}renderFeatures(e){if(!e.features)return F`<div class="placeholder">Loading features...</div>`;const t=e.features;return F`
      <div class="content active">
        <div class="features-grid">
          <div class="feature-card">
            <h4>🎥 Cameras</h4>
            <div class="feature-value">${t.cameras.length} found</div>
          </div>

          <div class="feature-card">
            <h4>📡 BLE Adapters</h4>
            <div class="feature-value">${t.ble_adapters.length} found</div>
            ${t.ble_adapters.length>0?F`<ul class="feature-list">
                  ${t.ble_adapters.map(e=>F`<li>${e.device}</li>`)}
                </ul>`:""}
          </div>

          <div class="feature-card">
            <h4>⚡ GPIO</h4>
            <div class="feature-value">${t.gpio.available?"✓ Available":"✗ Unavailable"}</div>
            ${t.gpio.chips.length>0?F`<div style="font-size: 11px; color: #666; margin-top: 4px;">
                  ${t.gpio.chips.length} chip${1!==t.gpio.chips.length?"s":""}
                </div>`:""}
          </div>

          <div class="feature-card">
            <h4>I²C</h4>
            <div class="feature-value">${t.i2c.available?"✓ Available":"✗ Unavailable"}</div>
            ${t.i2c.buses.length>0?F`<div style="font-size: 11px; color: #666; margin-top: 4px;">
                  ${t.i2c.buses.length} bus${1!==t.i2c.buses.length?"es":""}
                </div>`:""}
          </div>

          <div class="feature-card">
            <h4>🔊 Audio</h4>
            <div class="feature-value">${t.audio.available?"✓ Available":"✗ Unavailable"}</div>
            ${t.audio.cards.length>0?F`<ul class="feature-list">
                  ${t.audio.cards.map(e=>F`<li>${e.name}</li>`)}
                </ul>`:""}
          </div>

          <div class="feature-card">
            <h4>📡 UART</h4>
            <div class="feature-value">${t.uart.available?"✓ Available":"✗ Unavailable"}</div>
            ${t.uart.ports.length>0?F`<ul class="feature-list">
                  ${t.uart.ports.map(e=>F`<li>${e.device}</li>`)}
                </ul>`:""}
          </div>

          <div class="feature-card">
            <h4>🎬 GStreamer</h4>
            <div class="feature-value">
              ${t.gstreamer.available?"✓ "+(t.gstreamer.version||"?"):"✗ Not available"}
            </div>
          </div>

          <div class="feature-card">
            <h4>💾 Storage</h4>
            <div class="feature-value">${t.storage.length>0?t.storage[0].size:"Unknown"}</div>
            ${t.storage.length>0?F`<div style="font-size: 11px; color: #666; margin-top: 4px;">
                  Used: ${t.storage[0].used}
                </div>`:""}
          </div>

          ${Object.keys(t.hardware_config.dt_params).length>0?F`
                <div class="feature-card" style="grid-column: 1 / -1;">
                  <h4>⚙️ Device Tree Parameters</h4>
                  <ul class="feature-list">
                    ${Object.entries(t.hardware_config.dt_params).map(([e,t])=>F`<li><strong>${e}</strong> = ${t}</li>`)}
                  </ul>
                </div>
              `:""}
        </div>
      </div>
    `}renderServices(e){return e.services?0===e.services.length?F`<div class="placeholder">No services found</div>`:F`
      <div class="content active">
        <div class="service-list">
          ${e.services.map(t=>F`
              <div class="service-item ${this.selectedService?.id===t.id?"selected":""}">
                <div class="service-name">${t.name}</div>
                <div class="service-meta">
                  ID: <code>${t.id}</code> • v${t.version} • ${t.runtime}
                </div>
              </div>

              ${this.selectedService?.id===t.id?F`
                    <perimeter-control-service-access-editor
                      apiBaseUrl=${e.url}
                      serviceId=${t.id}
                    ></perimeter-control-service-access-editor>
                  `:""}
            `)}
        </div>
      </div>
    `:F`<div class="placeholder">Loading services...</div>`}};Object.defineProperty(Te,"styles",{enumerable:!0,configurable:!0,writable:!0,value:a`
    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --primary: #0288d1;
      --success: #4caf50;
      --warning: #ff9800;
      --error: #f44336;
    }

    .container {
      display: grid;
      grid-template-columns: 300px 1fr;
      gap: 20px;
      padding: 20px;
      background: #fafafa;
      min-height: 100vh;
    }

    .sidebar {
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }

    .main {
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      padding: 20px;
      overflow-y: auto;
    }

    .sidebar-header {
      padding: 16px;
      border-bottom: 1px solid #e0e0e0;
      font-weight: 600;
      color: var(--primary);
    }

    .node-list {
      flex: 1;
      overflow-y: auto;
    }

    .node-item {
      padding: 12px 16px;
      border-bottom: 1px solid #f0f0f0;
      cursor: pointer;
      transition: background 0.2s;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }

    .node-item:hover {
      background: #f5f5f5;
    }

    .node-item.selected {
      background: #e3f2fd;
      border-left: 3px solid var(--primary);
    }

    .node-status {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .node-status.online {
      background: var(--success);
      box-shadow: 0 0 6px rgba(76, 175, 80, 0.6);
    }

    .node-status.offline {
      background: #ccc;
    }

    .node-status.connecting {
      background: var(--warning);
      animation: pulse 1s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.6; }
    }

    .main-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid #e0e0e0;
    }

    .main-header h2 {
      margin: 0;
      font-size: 20px;
      color: #212121;
    }

    .refresh-btn {
      padding: 8px 12px;
      background: var(--primary);
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
    }

    .refresh-btn:hover {
      background: #0277bd;
    }

    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      border-bottom: 1px solid #e0e0e0;
    }

    .tab {
      padding: 8px 12px;
      cursor: pointer;
      border: none;
      background: none;
      color: #666;
      font-weight: 600;
      font-size: 13px;
      border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }

    .tab.active {
      color: var(--primary);
      border-bottom-color: var(--primary);
    }

    .tab:hover {
      color: var(--primary);
    }

    .content {
      display: none;
    }

    .content.active {
      display: block;
    }

    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
    }

    .feature-card {
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      padding: 12px;
      background: #f9f9f9;
    }

    .feature-card h4 {
      margin: 0 0 8px 0;
      font-size: 12px;
      font-weight: 600;
      color: #212121;
      text-transform: uppercase;
    }

    .feature-value {
      font-size: 13px;
      color: var(--primary);
      font-family: monospace;
    }

    .feature-list {
      font-size: 12px;
      color: #666;
      margin: 0;
      padding-left: 16px;
    }

    .feature-list li {
      margin: 4px 0;
    }

    .service-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .service-item {
      padding: 12px;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s;
    }

    .service-item:hover {
      background: #f9f9f9;
      border-color: var(--primary);
    }

    .service-item.selected {
      background: #e3f2fd;
      border-color: var(--primary);
    }

    .service-name {
      font-weight: 600;
      color: #212121;
      font-size: 13px;
    }

    .service-meta {
      font-size: 11px;
      color: #999;
      margin-top: 4px;
    }

    .placeholder {
      text-align: center;
      padding: 40px 20px;
      color: #999;
    }

    .placeholder-icon {
      font-size: 48px;
      margin-bottom: 16px;
      opacity: 0.3;
    }

    .error-box {
      background: #ffebee;
      border: 1px solid #ef5350;
      border-radius: 4px;
      padding: 12px;
      color: #c62828;
      font-size: 12px;
      margin-bottom: 16px;
    }

    @media (max-width: 768px) {
      .container {
        grid-template-columns: 1fr;
      }

      .sidebar {
        max-height: 200px;
      }
    }
  `}),e([he({type:Array})],Te.prototype,"nodes",void 0),e([he({type:Boolean})],Te.prototype,"autoRefresh",void 0),e([he({type:Number})],Te.prototype,"refreshInterval",void 0),e([ue()],Te.prototype,"selectedNode",void 0),e([ue()],Te.prototype,"selectedService",void 0),e([ue()],Te.prototype,"loading",void 0),e([ue()],Te.prototype,"error",void 0),Te=e([de("perimeter-control-fleet-view")],Te);let Ue=class extends Te{};Ue=e([de("isolator-fleet-view")],Ue);let Ie=class extends ne{constructor(){super(...arguments),Object.defineProperty(this,"hass",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"config",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"_deploying",{enumerable:!0,configurable:!0,writable:!0,value:!1}),Object.defineProperty(this,"_error",{enumerable:!0,configurable:!0,writable:!0,value:""}),Object.defineProperty(this,"_log",{enumerable:!0,configurable:!0,writable:!0,value:[]}),Object.defineProperty(this,"_dashboardActive",{enumerable:!0,configurable:!0,writable:!0,value:null}),Object.defineProperty(this,"_supervisorActive",{enumerable:!0,configurable:!0,writable:!0,value:null}),Object.defineProperty(this,"_pollTimer",{enumerable:!0,configurable:!0,writable:!0,value:null})}disconnectedCallback(){super.disconnectedCallback(),this._stopPolling()}_apiBase(){return"/api/perimeter_control"}async _fetchAuth(e,t){const i=this.hass?.auth?.data?.access_token??"";return fetch(e,{...t,headers:{Authorization:`Bearer ${i}`,"Content-Type":"application/json",...t?.headers??{}}})}async _onDeploy(){const e=this.config?.entryId;if(this.hass)if(e){this._error="",this._log=[],this._deploying=!0;try{const t=await this._fetchAuth(`${this._apiBase()}/${e}/deploy`,{method:"POST"});if(!t.ok){const e=await t.json().catch(()=>({}));return this._error=e.message??`Deploy request failed (${t.status})`,void(this._deploying=!1)}this._startPolling(e)}catch(e){this._error=`Network error: ${e?.message??String(e)}`,this._deploying=!1}}else this._error="entry_id not configured. Add entry_id to the card YAML (find it on the device page in Settings → Devices).";else this._error="No Home Assistant context available."}_startPolling(e){this._stopPolling(),this._pollTimer=setInterval(()=>this._poll(e),1500)}_stopPolling(){null!==this._pollTimer&&(clearInterval(this._pollTimer),this._pollTimer=null)}async _poll(e){try{const t=await this._fetchAuth(`${this._apiBase()}/${e}/status`);if(!t.ok)return;const i=await t.json();this._log=i.deploy_log,this._dashboardActive=i.dashboard_active,this._supervisorActive=i.supervisor_active,i.deploy_in_progress||(this._deploying=!1,this._stopPolling())}catch{}}render(){const e=this.config?.piHost??"Pi",t=this.config?.services??[],i=Boolean(this.config?.entryId),r=this._log[this._log.length-1],o=r?.percent??0,s=this._log.some(e=>e.error)||Boolean(this._error);return F`
            <div class="deploy-panel">
                <div class="panel-header">
                    <span class="panel-title">Deploy to Pi</span>
                    <span class="status-dot ${this._dashboardActive?"dot-ok":null===this._dashboardActive?"dot-unknown":"dot-err"}"
                          title="Dashboard service: ${this._dashboardActive?"active":"inactive"}"></span>
                </div>

                <div class="info-row">
                    <span class="info-label">Target</span>
                    <span class="info-value">${e}</span>
                </div>

                ${t.length>0?F`
                    <div class="info-row top-align">
                        <span class="info-label">Services</span>
                        <div class="chips">
                            ${t.map(e=>F`<span class="chip">${e}</span>`)}
                        </div>
                    </div>
                `:""}

                <button
                    class="deploy-btn"
                    @click=${this._onDeploy}
                    ?disabled=${this._deploying}
                >
                    ${this._deploying?F`<span class="spinner"></span> Deploying…`:"Deploy to Pi"}
                </button>

                ${this._deploying?F`
                    <div class="progress-bar-wrap">
                        <div class="progress-bar" style="width:${o}%"></div>
                    </div>
                `:""}

                ${this._error?F`
                    <div class="status-msg status-error">${this._error}</div>
                `:""}

                ${this._log.length>0?F`
                    <div class="log ${s?"log-error":""}">
                        ${this._log.map(e=>F`
                            <div class="log-row ${e.error?"log-row-error":""}">
                                <span class="log-phase">${e.phase}</span>
                                <span class="log-msg">${e.error??e.message}</span>
                            </div>
                        `)}
                    </div>
                `:""}

                ${i?"":F`
                    <details class="setup-hint">
                        <summary>Setup instructions</summary>
                        <ol>
                            <li>Install the <strong>Perimeter Control</strong> integration via HACS or manually copy <code>*.py, manifest.json</code> to <code>/config/custom_components/perimeter_control/</code>.</li>
                            <li>In HA go to <strong>Settings → Devices &amp; Services → Add Integration</strong> and search for <em>Perimeter Control</em>.</li>
                            <li>Complete the Add Device wizard (host, SSH key, services).</li>
                            <li>Copy the entry ID from the device page and add <code>entry_id: &lt;id&gt;</code> to this card's YAML.</li>
                        </ol>
                    </details>
                `}
            </div>
        `}};Object.defineProperty(Ie,"styles",{enumerable:!0,configurable:!0,writable:!0,value:a`
        :host {
            display: block;
        }

        .deploy-panel {
            padding: 12px 16px;
            border: 1px solid var(--divider-color, #e0e0e0);
            border-radius: 8px;
            background: var(--card-background-color, #fff);
            margin-top: 8px;
        }

        .panel-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
        }

        .panel-title {
            font-weight: 600;
            font-size: 14px;
            color: var(--primary-text-color);
            flex: 1;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .dot-ok      { background: var(--success-color, #43a047); }
        .dot-err     { background: var(--error-color,   #e53935); }
        .dot-unknown { background: var(--disabled-color, #bdbdbd); }

        .progress-bar-wrap {
            height: 3px;
            background: var(--divider-color, #e0e0e0);
            border-radius: 2px;
            margin: 8px 0 4px;
            overflow: hidden;
        }
        .progress-bar {
            height: 100%;
            background: var(--primary-color, #03a9f4);
            border-radius: 2px;
            transition: width 0.4s ease;
        }

        .log {
            margin-top: 8px;
            font-size: 11px;
            font-family: monospace;
            background: var(--code-background-color, #f5f5f5);
            border-radius: 4px;
            padding: 6px 8px;
            max-height: 140px;
            overflow-y: auto;
        }
        .log-error {
            border-left: 3px solid var(--error-color, #e53935);
        }
        .log-row {
            display: flex;
            gap: 6px;
            line-height: 1.6;
            color: var(--primary-text-color);
        }
        .log-row-error {
            color: var(--error-color, #c62828);
        }
        .log-phase {
            color: var(--secondary-text-color, #888);
            min-width: 72px;
            flex-shrink: 0;
        }

        .info-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
            font-size: 13px;
        }

        .info-row.top-align {
            align-items: flex-start;
        }

        .info-label {
            color: var(--secondary-text-color, #757575);
            min-width: 56px;
            flex-shrink: 0;
        }

        .info-value {
            color: var(--primary-text-color);
            font-family: monospace;
            font-size: 12px;
        }

        .chips {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }

        .chip {
            background: var(--primary-color, #03a9f4);
            color: #fff;
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 11px;
        }

        .deploy-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            width: 100%;
            margin-top: 10px;
            padding: 8px 16px;
            background: var(--primary-color, #03a9f4);
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: opacity 0.15s;
        }

        .deploy-btn:disabled {
            background: var(--disabled-color, #bdbdbd);
            cursor: default;
            opacity: 0.6;
        }

        .deploy-btn:not(:disabled):hover {
            opacity: 0.88;
        }

        .spinner {
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid rgba(255,255,255,0.4);
            border-top-color: #fff;
            border-radius: 50%;
            animation: spin 0.7s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .status-msg {
            margin-top: 8px;
            padding: 8px 10px;
            border-radius: 4px;
            font-size: 12px;
            line-height: 1.5;
        }

        .status-error {
            background: #ffebee;
            color: var(--error-color, #c62828);
            border-left: 3px solid var(--error-color, #c62828);
        }

        .setup-hint {
            margin-top: 10px;
            font-size: 12px;
            color: var(--secondary-text-color, #555);
        }

        .setup-hint summary {
            cursor: pointer;
            font-weight: 500;
            color: var(--primary-color, #03a9f4);
            user-select: none;
        }

        .setup-hint ol {
            margin: 8px 0 0 16px;
            padding: 0;
            line-height: 1.8;
        }

        pre {
            background: var(--code-background-color, #f5f5f5);
            border-radius: 4px;
            padding: 6px 8px;
            margin: 4px 0;
            font-size: 11px;
            overflow-x: auto;
            white-space: pre-wrap;
        }

        code {
            background: rgba(0, 0, 0, 0.06);
            border-radius: 3px;
            padding: 1px 4px;
            font-family: monospace;
            font-size: 11px;
        }
    `}),e([he({attribute:!1})],Ie.prototype,"hass",void 0),e([he({attribute:!1})],Ie.prototype,"config",void 0),e([ue()],Ie.prototype,"_deploying",void 0),e([ue()],Ie.prototype,"_error",void 0),e([ue()],Ie.prototype,"_log",void 0),e([ue()],Ie.prototype,"_dashboardActive",void 0),e([ue()],Ie.prototype,"_supervisorActive",void 0),Ie=e([de("perimeter-control-deploy-panel")],Ie);let ze=class extends Ie{};ze=e([de("isolator-deploy-panel")],ze);let De=class extends ne{constructor(){super(...arguments),Object.defineProperty(this,"hass",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"config",{enumerable:!0,configurable:!0,writable:!0,value:void 0})}setConfig(e){if(!e.service_id&&!e.show_deploy_panel)throw new Error("service_id is required unless show_deploy_panel is true");this.config=e}getConfigElement(){return F`
      <div style="padding: 16px;">
        <p>Edit the YAML configuration directly to configure this card.</p>
        <p><strong>Required:</strong> <code>service_id</code></p>
        <p><strong>Optional:</strong></p>
        <ul>
          <li><code>api_base_url</code> - default: <code>http://localhost:8080</code></li>
          <li><code>api_timeout_ms</code> - default: <code>10000</code> (ms)</li>
          <li><code>enable_error_details</code> - default: <code>false</code></li>
          <li><code>show_deploy_panel</code> - show Deploy to Pi panel (default: <code>false</code>)</li>
          <li><code>entry_id</code> - Perimeter Control integration entry ID (find in Settings → Devices &amp; Services)</li>
          <li><code>pi_host</code> - Pi address shown in deploy panel</li>
          <li><code>services</code> - list of service IDs to deploy</li>
        </ul>
      </div>
    `}static getStubConfig(){return{type:"custom:perimeter-control-card",service_id:"photo_booth",api_base_url:"http://localhost:8080"}}render(){if(!this.config)return F`<div>Configure this card</div>`;const e=this.config.api_base_url||"http://localhost:8080",t=this.config.api_timeout_ms||1e4,i=this.config.enable_error_details||!1,r=this.config.show_deploy_panel||!1,o=Boolean(this.config.service_id);return F`
      ${r?F`
        <perimeter-control-deploy-panel
          .hass=${this.hass}
          .config=${{entryId:this.config.entry_id,piHost:this.config.pi_host||e,services:this.config.services||[]}}
        ></perimeter-control-deploy-panel>
      `:""}
      ${o?F`
        <perimeter-control-error-boundary
          .config=${{title:"Perimeter Control",fallbackMessage:"Failed to load Perimeter Control. Check browser console for details.",showDetails:i}}
        >
          <perimeter-control-safe-loader
            .config=${{apiUrl:e,timeout:t,healthCheckPath:"/api/v1/services"}}
          >
            <perimeter-control-service-access-editor
              .apiBaseUrl=${e}
              .serviceId=${this.config.service_id}
            ></perimeter-control-service-access-editor>
          </perimeter-control-safe-loader>
        </perimeter-control-error-boundary>
      `:F`
        ${r?F``:F`<div>Configure this card</div>`}
      `}
    `}};e([he({attribute:!1})],De.prototype,"hass",void 0),e([he({attribute:!1})],De.prototype,"config",void 0),De=e([de("perimeter-control-card")],De);let Ne=class extends De{};Ne=e([de("isolator-service-access-card")],Ne),window.customCards=window.customCards||[],window.customCards.push({type:"perimeter-control-card",name:"Perimeter Control",description:"Control Isolator edge node access, fleet state, and deploy operations",preview:!1,documentationURL:"https://github.com/isolator/isolator#ha-integration"}),window.customCards.push({type:"isolator-service-access-card",name:"Perimeter Control (Legacy Type Alias)",description:"Backward-compatible alias. Prefer custom:perimeter-control-card.",preview:!1,documentationURL:"https://github.com/isolator/isolator#ha-integration"});let Re=class extends ne{constructor(){super(...arguments),Object.defineProperty(this,"hass",{enumerable:!0,configurable:!0,writable:!0,value:void 0})}render(){if(!this.hass)return F`<div>Loading...</div>`;try{const e=this.getPerimeterControlDevices();return F`
        <error-boundary>
          <div class="header">
            <h1>Perimeter Control</h1>
            <p>Manage your edge devices and services</p>
          </div>
  
          <div class="debug-info" style="background: #f5f5f5; padding: 8px; margin: 8px 0; border-radius: 4px; font-size: 12px;">
            <strong>Debug:</strong> Found ${e.length} devices, ${this.hass?Object.keys(this.hass.entities).length:0} total entities
          </div>
  
          ${0===e.length?this.renderNoDevices():this.renderDevices(e)}
  
          <div class="actions">
            <h2>Global Actions</h2>
            <div class="action-buttons">
              <button class="action-btn" @click=${this.deployAll}>
                Deploy All Devices
              </button>
              <button class="action-btn secondary" @click=${this.reloadConfig}>
                Reload Configurations
              </button>
              <button class="action-btn secondary" @click=${this.refreshDevices}>
                Refresh Device Info
              </button>
            </div>
          </div>
        </error-boundary>
      `}catch(e){return console.error("[Panel] Error in render:",e),F`
        <div style="color: red; padding: 16px; background: #ffe6e6; border-radius: 4px;">
          <h3>Panel Error</h3>
          <p>Failed to render Perimeter Control panel: ${e.message}</p>
        </div>
      `}}getPerimeterControlDevices(){const e=Object.values(this.hass?.entities||{}).filter(e=>{const t=e.attributes?.capability_id||e.attributes?.capability,i=e.entity_id.includes("perimeter_control"),r=e.attributes?.device||e.attributes?.friendly_name;return t||i||r&&(e.entity_id.includes("camera")||e.entity_id.includes("sensor")||e.entity_id.includes("button")||e.entity_id.includes("binary_sensor"))});if(0===e.length)return[];const t=this.groupEntitiesByDevice(e);return Object.entries(t).map(([e,t])=>({name:this.getDeviceNameFromEntities(t),host:this.getDeviceHostFromEntities(t),entities:t,status:this.getDeviceStatus(t),capabilities:this.getDeviceCapabilities(t)}))}groupEntitiesByDevice(e){const t={};return e.forEach(e=>{let i="default";const r=e.attributes?.device_info;if(r?.name)i=r.name;else if(r?.identifiers)i=r.identifiers[0]?.[1]||i;else if(e.attributes?.capability_id)i=e.attributes.capability_id;else if(e.attributes?.host)i=e.attributes.host;else{const t=e.entity_id.split(".");if(t.length>1){const e=t[1].split("_");e.length>2&&(i=e.slice(0,-1).join("_"))}}t[i]||(t[i]=[]),t[i].push(e)}),t}getDeviceNameFromEntities(e){for(const t of e){const e=t.attributes?.device_info?.name;if(e)return e}for(const t of e){const e=t.attributes?.capability_id||t.attributes?.capability;if(e)return e.replace("_"," ").replace(/\b\w/g,e=>e.toUpperCase())}const t=e[0];return t?.attributes?.friendly_name||t?.entity_id.split(".")[1].replace(/_/g," ")||"Unknown Device"}getDeviceHostFromEntities(e){for(const t of e){const e=t.attributes?.host;if(e)return e}for(const t of e){const e=t.attributes?.device_info;if(e?.configuration_url)try{return new URL(e.configuration_url).hostname}catch{}}return"192.168.50.47"}getDeviceCapabilities(e){const t=new Set;return e.forEach(e=>{const i=e.attributes?.capability_id||e.attributes?.capability;i&&t.add(i)}),Array.from(t)}getDeviceStatus(e){const t=e.filter(e=>{switch(e.entity_id.split(".")[0]){case"binary_sensor":return"on"===e.state;case"camera":default:return"unavailable"!==e.state;case"sensor":return"unknown"!==e.state&&"unavailable"!==e.state}}).length;return t>0?"connected":"disconnected"}renderNoDevices(){const e=this.hass?Object.keys(this.hass.entities):[];return F`
      <div class="no-devices">
        <h2>No Perimeter Control devices found</h2>
        <p>Add a Pi device by going to Settings → Devices & Services → Add Integration</p>
        
        <details style="margin-top: 16px; text-align: left;">
          <summary>Debug: All entities (${e.length})</summary>
          <div style="max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; margin: 8px 0;">
            ${e.map(e=>F`<div>${e}</div>`)}
          </div>
        </details>
      </div>
    `}renderDevices(e){return F`
      <div class="devices-grid">
        ${e.map(e=>F`
          <div class="device-card">
            <div class="device-header">
              <div class="device-icon">π</div>
              <div class="device-info">
                <h3>${e.name}</h3>
                <p>Host: ${e.host}</p>
                <p>Status: ${e.status}</p>
                ${e.capabilities?.length>0?F`
                  <p>Capabilities: ${e.capabilities.join(", ")}</p>
                `:""}
              </div>
            </div>
            
            <div class="entities-grid">
              ${e.entities.map(e=>this.renderGenericEntity(e))}
              ${e.host?this.renderDashboardLinks(e.host,e.capabilities):""}
            </div>
          </div>
        `)}
      </div>
    `}renderGenericEntity(e){const t=e.entity_id.split(".")[0],i=e.attributes?.friendly_name||e.entity_id.split(".")[1].replace(/_/g," "),r=e.attributes?.capability_id||e.attributes?.capability;return F`
      <div class="entity-card">
        <div class="entity-header">
          <div class="entity-name">${i}</div>
          <div class="entity-status status-${this.getEntityStatusClass(e)}">
            ${this.getEntityDisplayValue(e)}
          </div>
        </div>
        
        ${r?F`<div class="entity-capability">${r}</div>`:""}
        ${this.renderEntityActions(e,t)}
      </div>
    `}getEntityStatusClass(e){switch(e.entity_id.split(".")[0]){case"binary_sensor":return"on"===e.state?"active":"inactive";case"camera":return"unavailable"!==e.state?"active":"inactive";case"sensor":return"unknown"!==e.state&&"unavailable"!==e.state?"active":"inactive";case"button":return"available";default:return"unavailable"===e.state?"inactive":"active"}}getEntityDisplayValue(e){switch(e.entity_id.split(".")[0]){case"binary_sensor":return"on"===e.state?"Active":"Inactive";case"camera":return"unavailable"!==e.state?"Streaming":"Offline";case"sensor":const t=e.attributes?.unit_of_measurement;return t?`${e.state} ${t}`:e.state;case"button":return"Ready";default:return e.state}}renderEntityActions(e,t){switch(t){case"button":return F`
          <div class="entity-actions">
            <button class="action-btn" @click=${()=>this.callEntityService(e.entity_id,"press")}>
              Press
            </button>
          </div>
        `;case"camera":return F`
          <div class="entity-actions">
            <button class="action-btn" @click=${()=>this.showCameraEntity(e.entity_id)}>
              📷 View
            </button>
          </div>
        `;case"binary_sensor":case"sensor":return F`
          <div class="entity-actions">
            <button class="action-btn secondary" @click=${()=>this.showEntityInfo(e.entity_id)}>
              ℹ️ Details
            </button>
          </div>
        `;default:return F`
          <div class="entity-actions">
            <button class="action-btn secondary" @click=${()=>this.showEntityInfo(e.entity_id)}>
              View
            </button>
          </div>
        `}}renderDashboardLinks(e,t=[]){return F`
      <div class="entity-card dashboard-links">
        <div class="entity-header">
          <div class="entity-name">Web Dashboards</div>
          <div class="entity-status status-available">available</div>
        </div>
        
        <div class="entity-actions" style="display: flex; gap: 4px; flex-wrap: wrap;">
          <button class="action-btn" @click=${()=>this.openDashboard(e,8080)} style="font-size: 11px; padding: 4px 8px;">
            🌐 API
          </button>
          
          ${t.map(t=>F`
            <button class="action-btn secondary" @click=${()=>this.openCapabilityDashboard(e,t)} style="font-size: 11px; padding: 4px 8px;">
              📊 ${t}
            </button>
          `)}
        </div>
      </div>
    `}openDashboard(e,t){const i=`http://${e}:${t}`;window.open(i,"_blank")}async callEntityService(e,t){try{const i=e.split(".")[0];await(this.hass?.callService(i,t,{entity_id:e}))}catch(i){console.error(`Failed to call ${t} on ${e}:`,i)}}showCameraEntity(e){const t=new CustomEvent("hass-more-info",{detail:{entityId:e},bubbles:!0,composed:!0});this.dispatchEvent(t)}showEntityInfo(e){const t=new CustomEvent("hass-more-info",{detail:{entityId:e},bubbles:!0,composed:!0});this.dispatchEvent(t)}openCapabilityDashboard(e,t){const i=`http://${e}:${{photo_booth:8093,wildlife_monitor:8094,ble_gatt_repeater:8091,network_isolator:5006}[t]||3e3}`;window.open(i,"_blank")}async deployAll(){try{await(this.hass?.callService("perimeter_control","deploy",{force:!0}))}catch(e){console.error("Deploy failed:",e)}}async reloadConfig(){try{await(this.hass?.callService("perimeter_control","reload_config",{}))}catch(e){console.error("Reload config failed:",e)}}async refreshDevices(){try{await(this.hass?.callService("perimeter_control","get_device_info",{}))}catch(e){console.error("Get device info failed:",e)}}};Object.defineProperty(Re,"styles",{enumerable:!0,configurable:!0,writable:!0,value:a`
    :host {
      display: block;
      padding: 16px;
      max-width: 1200px;
      margin: 0 auto;
    }

    .header {
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
      padding-bottom: 16px;
      margin-bottom: 24px;
    }

    .header h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 400;
      color: var(--primary-text-color);
    }

    .header p {
      margin: 8px 0 0 0;
      color: var(--secondary-text-color);
    }

    .devices-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
      gap: 16px;
    }

    .device-card {
      background: var(--card-background-color);
      border-radius: 8px;
      padding: 16px;
      border: 1px solid var(--divider-color);
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .device-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }

    .device-icon {
      width: 32px;
      height: 32px;
      background: var(--primary-color);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
    }

    .device-info h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
    }

    .device-info p {
      margin: 4px 0 0 0;
      font-size: 14px;
      color: var(--secondary-text-color);
    }

    .entities-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }

    .entity-card {
      background: var(--card-background-color, #fafafa);
      border-radius: 4px;
      padding: 8px;
      border: 1px solid var(--divider-color);
      font-size: 12px;
    }

    .entity-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
    }

    .entity-name {
      font-weight: 500;
      font-size: 11px;
    }

    .entity-capability {
      font-size: 10px;
      color: var(--secondary-text-color);
      margin-bottom: 4px;
    }

    .entity-status {
      padding: 1px 6px;
      border-radius: 8px;
      font-size: 10px;
      font-weight: 500;
    }

    .entity-actions {
      margin-top: 6px;
    }

    .entity-actions .action-btn {
      padding: 4px 8px;
      font-size: 10px;
      margin-right: 4px;
    }

    .dashboard-links {
      background: var(--primary-color);
      color: white;
    }

    .dashboard-links .entity-name {
      color: white;
    }

    .dashboard-links .entity-status {
      background: rgba(255,255,255,0.2);
      color: white;
    }

    .actions {
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--divider-color);
    }

    .actions h2 {
      margin: 0 0 16px 0;
      font-size: 18px;
      font-weight: 500;
    }

    .action-buttons {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .action-btn {
      padding: 8px 16px;
      border: 1px solid var(--primary-color);
      background: var(--primary-color);
      color: white;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }

    .action-btn:hover {
      background: var(--primary-color);
      opacity: 0.9;
    }

    .action-btn.secondary {
      background: transparent;
      color: var(--primary-color);
    }

    .action-btn.secondary:hover {
      background: var(--primary-color);
      color: white;
    }

    .no-devices {
      text-align: center;
      padding: 48px 16px;
      color: var(--secondary-text-color);
    }

    .no-devices h2 {
      color: var(--primary-text-color);
      margin-bottom: 8px;
    }

    .status-unknown { background: #e0e0e0; color: #666; }
    .status-active { background: #c8e6c9; color: #2e7d32; }
    .status-inactive { background: #ffcdd2; color: #c62828; }
    .status-available { background: #e1f5fe; color: #0277bd; }
    .status-running { background: #c8e6c9; color: #2e7d32; }
    .status-stopped { background: #ffcdd2; color: #c62828; }
  `}),e([he({attribute:!1})],Re.prototype,"hass",void 0),Re=e([de("perimeter-control-panel")],Re);export{Ie as DeployPanel,fe as ErrorBoundary,Te as FleetView,Re as PerimeterControlPanel,ge as SafeLoader,De as ServiceAccessCard,me as ServiceAccessEditor};

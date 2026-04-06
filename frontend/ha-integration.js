function t(t,e,i,s){var r,n=arguments.length,o=n<3?e:null===s?s=Object.getOwnPropertyDescriptor(e,i):s;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)o=Reflect.decorate(t,e,i,s);else for(var a=t.length-1;a>=0;a--)(r=t[a])&&(o=(n<3?r(o):n>3?r(e,i,o):r(e,i))||o);return n>3&&o&&Object.defineProperty(e,i,o),o}"function"==typeof SuppressedError&&SuppressedError;const e=globalThis,i=e.ShadowRoot&&(void 0===e.ShadyCSS||e.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),r=new WeakMap;let n=class{constructor(t,e,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(i&&void 0===t){const i=void 0!==e&&1===e.length;i&&(t=r.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&r.set(e,t))}return t}toString(){return this.cssText}};const o=i?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new n("string"==typeof t?t:t+"",void 0,s))(e)})(t):t,{is:a,defineProperty:c,getOwnPropertyDescriptor:l,getOwnPropertyNames:d,getOwnPropertySymbols:h,getPrototypeOf:p}=Object,u=globalThis,f=u.trustedTypes,b=f?f.emptyScript:"",y=u.reactiveElementPolyfillSupport,g=(t,e)=>t,v={toAttribute(t,e){switch(e){case Boolean:t=t?b:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},m=(t,e)=>!a(t,e),$={attribute:!0,type:String,converter:v,reflect:!1,useDefault:!1,hasChanged:m};Symbol.metadata??=Symbol("metadata"),u.litPropertyMetadata??=new WeakMap;let _=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=$){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const i=Symbol(),s=this.getPropertyDescriptor(t,i,e);void 0!==s&&c(this.prototype,t,s)}}static getPropertyDescriptor(t,e,i){const{get:s,set:r}=l(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:s,set(e){const n=s?.call(this);r?.call(this,e),this.requestUpdate(t,n,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??$}static _$Ei(){if(this.hasOwnProperty(g("elementProperties")))return;const t=p(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(g("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(g("properties"))){const t=this.properties,e=[...d(t),...h(t)];for(const i of e)this.createProperty(i,t[i])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,i]of e)this.elementProperties.set(t,i)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const i=this._$Eu(t,e);void 0!==i&&this._$Eh.set(i,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(o(t))}else void 0!==t&&e.push(o(t));return e}static _$Eu(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((t,s)=>{if(i)t.adoptedStyleSheets=s.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const i of s){const s=document.createElement("style"),r=e.litNonce;void 0!==r&&s.setAttribute("nonce",r),s.textContent=i.cssText,t.appendChild(s)}})(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){const i=this.constructor.elementProperties.get(t),s=this.constructor._$Eu(t,i);if(void 0!==s&&!0===i.reflect){const r=(void 0!==i.converter?.toAttribute?i.converter:v).toAttribute(e,i.type);this._$Em=t,null==r?this.removeAttribute(s):this.setAttribute(s,r),this._$Em=null}}_$AK(t,e){const i=this.constructor,s=i._$Eh.get(t);if(void 0!==s&&this._$Em!==s){const t=i.getPropertyOptions(s),r="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:v;this._$Em=s;const n=r.fromAttribute(e,t.type);this[s]=n??this._$Ej?.get(s)??n,this._$Em=null}}requestUpdate(t,e,i,s=!1,r){if(void 0!==t){const n=this.constructor;if(!1===s&&(r=this[t]),i??=n.getPropertyOptions(t),!((i.hasChanged??m)(r,e)||i.useDefault&&i.reflect&&r===this._$Ej?.get(t)&&!this.hasAttribute(n._$Eu(t,i))))return;this.C(t,e,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:s,wrapped:r},n){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,n??e??this[t]),!0!==r||void 0!==n)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),!0===s&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,i]of t){const{wrapped:t}=i,s=this[e];!0!==t||this._$AL.has(e)||void 0===s||this.C(e,void 0,i,s)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[g("elementProperties")]=new Map,_[g("finalized")]=new Map,y?.({ReactiveElement:_}),(u.reactiveElementVersions??=[]).push("2.1.2");const x=globalThis,A=t=>t,E=x.trustedTypes,w=E?E.createPolicy("lit-html",{createHTML:t=>t}):void 0,S="$lit$",k=`lit$${Math.random().toFixed(9).slice(2)}$`,C="?"+k,P=`<${C}>`,O=document,D=()=>O.createComment(""),U=t=>null===t||"object"!=typeof t&&"function"!=typeof t,M=Array.isArray,H="[ \t\n\f\r]",N=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,R=/-->/g,j=/>/g,z=RegExp(`>|${H}(?:([^\\s"'>=/]+)(${H}*=${H}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),T=/'/g,I=/"/g,L=/^(?:script|style|textarea|title)$/i,B=(t=>(e,...i)=>({_$litType$:t,strings:e,values:i}))(1),V=Symbol.for("lit-noChange"),W=Symbol.for("lit-nothing"),q=new WeakMap,F=O.createTreeWalker(O,129);function G(t,e){if(!M(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==w?w.createHTML(e):e}const J=(t,e)=>{const i=t.length-1,s=[];let r,n=2===e?"<svg>":3===e?"<math>":"",o=N;for(let e=0;e<i;e++){const i=t[e];let a,c,l=-1,d=0;for(;d<i.length&&(o.lastIndex=d,c=o.exec(i),null!==c);)d=o.lastIndex,o===N?"!--"===c[1]?o=R:void 0!==c[1]?o=j:void 0!==c[2]?(L.test(c[2])&&(r=RegExp("</"+c[2],"g")),o=z):void 0!==c[3]&&(o=z):o===z?">"===c[0]?(o=r??N,l=-1):void 0===c[1]?l=-2:(l=o.lastIndex-c[2].length,a=c[1],o=void 0===c[3]?z:'"'===c[3]?I:T):o===I||o===T?o=z:o===R||o===j?o=N:(o=z,r=void 0);const h=o===z&&t[e+1].startsWith("/>")?" ":"";n+=o===N?i+P:l>=0?(s.push(a),i.slice(0,l)+S+i.slice(l)+k+h):i+k+(-2===l?e:h)}return[G(t,n+(t[i]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),s]};class K{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let r=0,n=0;const o=t.length-1,a=this.parts,[c,l]=J(t,e);if(this.el=K.createElement(c,i),F.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(s=F.nextNode())&&a.length<o;){if(1===s.nodeType){if(s.hasAttributes())for(const t of s.getAttributeNames())if(t.endsWith(S)){const e=l[n++],i=s.getAttribute(t).split(k),o=/([.?@])?(.*)/.exec(e);a.push({type:1,index:r,name:o[2],strings:i,ctor:"."===o[1]?tt:"?"===o[1]?et:"@"===o[1]?it:Y}),s.removeAttribute(t)}else t.startsWith(k)&&(a.push({type:6,index:r}),s.removeAttribute(t));if(L.test(s.tagName)){const t=s.textContent.split(k),e=t.length-1;if(e>0){s.textContent=E?E.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],D()),F.nextNode(),a.push({type:2,index:++r});s.append(t[e],D())}}}else if(8===s.nodeType)if(s.data===C)a.push({type:2,index:r});else{let t=-1;for(;-1!==(t=s.data.indexOf(k,t+1));)a.push({type:7,index:r}),t+=k.length-1}r++}}static createElement(t,e){const i=O.createElement("template");return i.innerHTML=t,i}}function Z(t,e,i=t,s){if(e===V)return e;let r=void 0!==s?i._$Co?.[s]:i._$Cl;const n=U(e)?void 0:e._$litDirective$;return r?.constructor!==n&&(r?._$AO?.(!1),void 0===n?r=void 0:(r=new n(t),r._$AT(t,i,s)),void 0!==s?(i._$Co??=[])[s]=r:i._$Cl=r),void 0!==r&&(e=Z(t,r._$AS(t,e.values),r,s)),e}class Q{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:i}=this._$AD,s=(t?.creationScope??O).importNode(e,!0);F.currentNode=s;let r=F.nextNode(),n=0,o=0,a=i[0];for(;void 0!==a;){if(n===a.index){let e;2===a.type?e=new X(r,r.nextSibling,this,t):1===a.type?e=new a.ctor(r,a.name,a.strings,this,t):6===a.type&&(e=new st(r,this,t)),this._$AV.push(e),a=i[++o]}n!==a?.index&&(r=F.nextNode(),n++)}return F.currentNode=O,s}p(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class X{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,s){this.type=2,this._$AH=W,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=Z(this,t,e),U(t)?t===W||null==t||""===t?(this._$AH!==W&&this._$AR(),this._$AH=W):t!==this._$AH&&t!==V&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>M(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==W&&U(this._$AH)?this._$AA.nextSibling.data=t:this.T(O.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:i}=t,s="number"==typeof i?this._$AC(t):(void 0===i.el&&(i.el=K.createElement(G(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(e);else{const t=new Q(s,this),i=t.u(this.options);t.p(e),this.T(i),this._$AH=t}}_$AC(t){let e=q.get(t.strings);return void 0===e&&q.set(t.strings,e=new K(t)),e}k(t){M(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const r of t)s===e.length?e.push(i=new X(this.O(D()),this.O(D()),this,this.options)):i=e[s],i._$AI(r),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const e=A(t).nextSibling;A(t).remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class Y{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,s,r){this.type=1,this._$AH=W,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=r,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=W}_$AI(t,e=this,i,s){const r=this.strings;let n=!1;if(void 0===r)t=Z(this,t,e,0),n=!U(t)||t!==this._$AH&&t!==V,n&&(this._$AH=t);else{const s=t;let o,a;for(t=r[0],o=0;o<r.length-1;o++)a=Z(this,s[i+o],e,o),a===V&&(a=this._$AH[o]),n||=!U(a)||a!==this._$AH[o],a===W?t=W:t!==W&&(t+=(a??"")+r[o+1]),this._$AH[o]=a}n&&!s&&this.j(t)}j(t){t===W?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class tt extends Y{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===W?void 0:t}}class et extends Y{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==W)}}class it extends Y{constructor(t,e,i,s,r){super(t,e,i,s,r),this.type=5}_$AI(t,e=this){if((t=Z(this,t,e,0)??W)===V)return;const i=this._$AH,s=t===W&&i!==W||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,r=t!==W&&(i===W||s);s&&this.element.removeEventListener(this.name,this,i),r&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class st{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){Z(this,t)}}const rt=x.litHtmlPolyfillSupport;rt?.(K,X),(x.litHtmlVersions??=[]).push("3.3.2");const nt=globalThis;class ot extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{const s=i?.renderBefore??e;let r=s._$litPart$;if(void 0===r){const t=i?.renderBefore??null;s._$litPart$=r=new X(e.insertBefore(D(),t),t,void 0,i??{})}return r._$AI(t),r})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return V}}ot._$litElement$=!0,ot.finalized=!0,nt.litElementHydrateSupport?.({LitElement:ot});const at=nt.litElementPolyfillSupport;at?.({LitElement:ot}),(nt.litElementVersions??=[]).push("4.2.2");const ct={attribute:!0,type:String,converter:v,reflect:!1,hasChanged:m},lt=(t=ct,e,i)=>{const{kind:s,metadata:r}=i;let n=globalThis.litPropertyMetadata.get(r);if(void 0===n&&globalThis.litPropertyMetadata.set(r,n=new Map),"setter"===s&&((t=Object.create(t)).wrapped=!0),n.set(i.name,t),"accessor"===s){const{name:s}=i;return{set(i){const r=e.get.call(this);e.set.call(this,i),this.requestUpdate(s,r,t,!0,i)},init(e){return void 0!==e&&this.C(s,void 0,t,e),e}}}if("setter"===s){const{name:s}=i;return function(i){const r=this[s];e.call(this,i),this.requestUpdate(s,r,t,!0,i)}}throw Error("Unsupported decorator location: "+s)};function dt(t){return(e,i)=>"object"==typeof i?lt(t,e,i):((t,e,i)=>{const s=e.hasOwnProperty(i);return e.constructor.createProperty(i,t),s?Object.getOwnPropertyDescriptor(e,i):void 0})(t,e,i)}let ht=class extends ot{constructor(){super(),Object.defineProperty(this,"hass",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"errorMessage",{enumerable:!0,configurable:!0,writable:!0,value:null}),Object.defineProperty(this,"errorStack",{enumerable:!0,configurable:!0,writable:!0,value:null}),Object.defineProperty(this,"isInitialized",{enumerable:!0,configurable:!0,writable:!0,value:!1})}firstUpdated(){this.isInitialized=!0}handleError(t){console.error("Panel Error:",t),this.errorMessage=t.message||"Unknown error occurred",this.errorStack=t.stack||"No stack trace available"}render(){if(!this.hass||!this.isInitialized)return B`
        <div style="padding: 16px; text-align: center;">
          <p>Loading Home Assistant connection...</p>
        </div>
      `;if(this.errorMessage)return this.renderError();try{if(!this.hass.entities)return B`
          <div style="padding: 16px; text-align: center;">
            <p>Waiting for Home Assistant entities...</p>
          </div>
        `;const t=this.getPerimeterControlDevices();return B`
        <div class="header">
          <h1>Perimeter Control</h1>
          <p>Manage your edge devices and services</p>
        </div>

        <div class="debug-info" style="background: #f5f5f5; padding: 8px; margin: 8px 0; border-radius: 4px; font-size: 12px;">
          <strong>Debug:</strong> Found ${t.length} devices, ${this.hass?Object.keys(this.hass.entities).length:0} total entities
          <br><strong>Sample entities:</strong> ${this.hass?Object.keys(this.hass.entities).slice(0,5).join(", "):"None"}
          <br><strong>Perimeter entities:</strong> ${this.hass?Object.keys(this.hass.entities).filter(t=>t.includes("perimeter")).join(", "):"None"}
        </div>

        ${0===t.length?this.renderNoDevices():this.renderDevices(t)}

        <div class="actions">
          <h2>Global Actions</h2>
          <div class="action-buttons">
            <button class="action-btn" @click=${()=>this.safeAction(this.deployAll)}>
              Deploy All Devices
            </button>
            <button class="action-btn secondary" @click=${()=>this.safeAction(this.reloadConfig)}>
              Reload Configurations
            </button>
            <button class="action-btn secondary" @click=${()=>this.safeAction(this.refreshDevices)}>
              Refresh Device Info
            </button>
          </div>
        </div>
      `}catch(t){return console.error("[Panel] Error in render:",t),this.handleError(t instanceof Error?t:new Error(String(t))),this.renderError()}}renderError(){return B`
      <div class="error-display">
        <div class="error-title">
          <span>⚠️</span>
          <span>Perimeter Control Panel Error</span>
        </div>
        <div class="error-message">
          ${this.errorMessage}
        </div>
        ${this.errorStack?B`
          <details>
            <summary style="cursor: pointer; margin-bottom: 8px;">Show stack trace</summary>
            <div class="error-stack">${this.errorStack}</div>
          </details>
        `:""}
        <div class="error-actions">
          <button class="error-btn" @click=${this.clearError}>
            Clear Error
          </button>
          <button class="error-btn secondary" @click=${this.reloadPanel}>
            Reload Panel
          </button>
        </div>
      </div>
    `}clearError(){this.errorMessage=null,this.errorStack=null}reloadPanel(){this.clearError(),this.requestUpdate()}async safeAction(t){try{await t()}catch(t){this.handleError(t instanceof Error?t:new Error(String(t)))}}getPerimeterControlDevices(){try{if(!this.hass||!this.hass.entities)return[];const t=Object.values(this.hass.entities||{}).filter(t=>{try{const e=t.attributes?.capability_id||t.attributes?.capability,i=t.entity_id.includes("perimeter_control"),s=t.attributes?.device||t.attributes?.friendly_name;return e||i||s&&(t.entity_id.includes("camera")||t.entity_id.includes("sensor")||t.entity_id.includes("button")||t.entity_id.includes("binary_sensor"))}catch(e){return console.warn("Error filtering entity:",t.entity_id,e),!1}});if(0===t.length)return[];const e=this.groupEntitiesByDevice(t);return Object.entries(e).map(([t,e])=>({name:this.getDeviceNameFromEntities(e),host:this.getDeviceHostFromEntities(e),entities:e,status:this.getDeviceStatus(e),capabilities:this.getDeviceCapabilities(e)}))}catch(t){return console.error("Error getting Perimeter Control devices:",t),[]}}groupEntitiesByDevice(t){const e={};return t.forEach(t=>{let i="default";const s=t.attributes?.device_info;if(s?.name)i=s.name;else if(s?.identifiers)i=s.identifiers[0]?.[1]||i;else if(t.attributes?.capability_id)i=t.attributes.capability_id;else if(t.attributes?.host)i=t.attributes.host;else{const e=t.entity_id.split(".");if(e.length>1){const t=e[1].split("_");t.length>2&&(i=t.slice(0,-1).join("_"))}}e[i]||(e[i]=[]),e[i].push(t)}),e}getDeviceNameFromEntities(t){for(const e of t){const t=e.attributes?.device_info?.name;if(t)return t}for(const e of t){const t=e.attributes?.capability_id||e.attributes?.capability;if(t)return t.replace("_"," ").replace(/\b\w/g,t=>t.toUpperCase())}const e=t[0];return e?.attributes?.friendly_name||e?.entity_id.split(".")[1].replace(/_/g," ")||"Unknown Device"}getDeviceHostFromEntities(t){for(const e of t){const t=e.attributes?.host;if(t)return t}for(const e of t){const t=e.attributes?.device_info;if(t?.configuration_url)try{return new URL(t.configuration_url).hostname}catch{}}return"192.168.50.47"}getDeviceCapabilities(t){const e=new Set;return t.forEach(t=>{const i=t.attributes?.capability_id||t.attributes?.capability;i&&e.add(i)}),Array.from(e)}getDeviceStatus(t){const e=t.filter(t=>{switch(t.entity_id.split(".")[0]){case"binary_sensor":return"on"===t.state;case"camera":default:return"unavailable"!==t.state;case"sensor":return"unknown"!==t.state&&"unavailable"!==t.state}}).length;return e>0?"connected":"disconnected"}renderNoDevices(){const t=this.hass?Object.keys(this.hass.entities):[];return B`
      <div class="no-devices">
        <h2>No Perimeter Control devices found</h2>
        <p>Add a Pi device by going to Settings → Devices & Services → Add Integration</p>
        
        <details style="margin-top: 16px; text-align: left;">
          <summary>Debug: All entities (${t.length})</summary>
          <div style="max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; margin: 8px 0;">
            ${t.map(t=>B`<div>${t}</div>`)}
          </div>
        </details>
      </div>
    `}renderDevices(t){return B`
      <div class="devices-grid">
        ${t.map(t=>B`
          <div class="device-card">
            <div class="device-header">
              <div class="device-icon">π</div>
              <div class="device-info">
                <h3>${t.name}</h3>
                <p>Host: ${t.host}</p>
                <p>Status: ${t.status}</p>
                ${t.capabilities?.length>0?B`
                  <p>Capabilities: ${t.capabilities.join(", ")}</p>
                `:""}
              </div>
            </div>
            
            <div class="entities-grid">
              ${t.entities.map(t=>this.renderGenericEntity(t))}
              ${t.host?this.renderDashboardLinks(t.host,t.capabilities):""}
            </div>
          </div>
        `)}
      </div>
    `}renderGenericEntity(t){const e=t.entity_id.split(".")[0],i=t.attributes?.friendly_name||t.entity_id.split(".")[1].replace(/_/g," "),s=t.attributes?.capability_id||t.attributes?.capability;return B`
      <div class="entity-card">
        <div class="entity-header">
          <div class="entity-name">${i}</div>
          <div class="entity-status status-${this.getEntityStatusClass(t)}">
            ${this.getEntityDisplayValue(t)}
          </div>
        </div>
        
        ${s?B`<div class="entity-capability">${s}</div>`:""}
        ${this.renderEntityActions(t,e)}
      </div>
    `}getEntityStatusClass(t){switch(t.entity_id.split(".")[0]){case"binary_sensor":return"on"===t.state?"active":"inactive";case"camera":return"unavailable"!==t.state?"active":"inactive";case"sensor":return"unknown"!==t.state&&"unavailable"!==t.state?"active":"inactive";case"button":return"available";default:return"unavailable"===t.state?"inactive":"active"}}getEntityDisplayValue(t){switch(t.entity_id.split(".")[0]){case"binary_sensor":return"on"===t.state?"Active":"Inactive";case"camera":return"unavailable"!==t.state?"Streaming":"Offline";case"sensor":const e=t.attributes?.unit_of_measurement;return e?`${t.state} ${e}`:t.state;case"button":return"Ready";default:return t.state}}renderEntityActions(t,e){switch(e){case"button":return B`
          <div class="entity-actions">
            <button class="action-btn" @click=${()=>this.callEntityService(t.entity_id,"press")}>
              Press
            </button>
          </div>
        `;case"camera":return B`
          <div class="entity-actions">
            <button class="action-btn" @click=${()=>this.showCameraEntity(t.entity_id)}>
              📷 View
            </button>
          </div>
        `;case"binary_sensor":case"sensor":return B`
          <div class="entity-actions">
            <button class="action-btn secondary" @click=${()=>this.showEntityInfo(t.entity_id)}>
              ℹ️ Details
            </button>
          </div>
        `;default:return B`
          <div class="entity-actions">
            <button class="action-btn secondary" @click=${()=>this.showEntityInfo(t.entity_id)}>
              View
            </button>
          </div>
        `}}renderDashboardLinks(t,e=[]){return B`
      <div class="entity-card dashboard-links">
        <div class="entity-header">
          <div class="entity-name">Web Dashboards</div>
          <div class="entity-status status-available">available</div>
        </div>
        
        <div class="entity-actions" style="display: flex; gap: 4px; flex-wrap: wrap;">
          <button class="action-btn" @click=${()=>this.openDashboard(t,8080)} style="font-size: 11px; padding: 4px 8px;">
            🌐 API
          </button>
          
          ${e.map(e=>B`
            <button class="action-btn secondary" @click=${()=>this.openCapabilityDashboard(t,e)} style="font-size: 11px; padding: 4px 8px;">
              📊 ${e}
            </button>
          `)}
        </div>
      </div>
    `}openDashboard(t,e){const i=`http://${t}:${e}`;window.open(i,"_blank")}async callEntityService(t,e){try{const i=t.split(".")[0];await(this.hass?.callService(i,e,{entity_id:t}))}catch(i){console.error(`Failed to call ${e} on ${t}:`,i)}}showCameraEntity(t){const e=new CustomEvent("hass-more-info",{detail:{entityId:t},bubbles:!0,composed:!0});this.dispatchEvent(e)}showEntityInfo(t){const e=new CustomEvent("hass-more-info",{detail:{entityId:t},bubbles:!0,composed:!0});this.dispatchEvent(e)}openCapabilityDashboard(t,e){const i=`http://${t}:${{photo_booth:8093,wildlife_monitor:8094,ble_gatt_repeater:8091,network_isolator:5006}[e]||3e3}`;window.open(i,"_blank")}async deployAll(){await(this.hass?.callService("perimeter_control","deploy",{force:!0}))}async reloadConfig(){await(this.hass?.callService("perimeter_control","reload_config",{}))}async refreshDevices(){await(this.hass?.callService("perimeter_control","get_device_info",{}))}};Object.defineProperty(ht,"styles",{enumerable:!0,configurable:!0,writable:!0,value:((t,...e)=>{const i=1===t.length?t[0]:e.reduce((e,i,s)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[s+1],t[0]);return new n(i,t,s)})`
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

    .error-display {
      background: #ffebee;
      border: 1px solid #f44336;
      border-radius: 4px;
      padding: 16px;
      margin: 16px 0;
      color: #c62828;
    }

    .error-title {
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .error-message {
      margin-bottom: 12px;
      font-family: monospace;
      font-size: 14px;
    }

    .error-stack {
      white-space: pre-wrap;
      font-family: monospace;
      font-size: 12px;
      background: #fff;
      border: 1px solid #ddd;
      border-radius: 4px;
      padding: 8px;
      max-height: 200px;
      overflow-y: auto;
      margin-top: 8px;
    }

    .error-actions {
      display: flex;
      gap: 8px;
      margin-top: 12px;
    }

    .error-btn {
      padding: 6px 12px;
      border: 1px solid #f44336;
      background: #f44336;
      color: white;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }

    .error-btn:hover {
      background: #d32f2f;
    }

    .error-btn.secondary {
      background: transparent;
      color: #f44336;
    }

    .error-btn.secondary:hover {
      background: #ffebee;
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
  `}),t([dt({attribute:!1})],ht.prototype,"hass",void 0),t([dt({state:!0})],ht.prototype,"errorMessage",void 0),t([dt({state:!0})],ht.prototype,"errorStack",void 0),t([dt({state:!0})],ht.prototype,"isInitialized",void 0),ht=t([(t=>(e,i)=>{void 0!==i?i.addInitializer(()=>{customElements.define(t,e)}):customElements.define(t,e)})("perimeter-control-panel")],ht);export{ht as PerimeterControlPanel};

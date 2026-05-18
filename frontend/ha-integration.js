const t=globalThis,e=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),i=new WeakMap;let r=class{constructor(t,e,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const s=this.t;if(e&&void 0===t){const e=void 0!==s&&1===s.length;e&&(t=i.get(s)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),e&&i.set(s,t))}return t}toString(){return this.cssText}};const o=e?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const s of t.cssRules)e+=s.cssText;return(t=>new r("string"==typeof t?t:t+"",void 0,s))(e)})(t):t,{is:n,defineProperty:a,getOwnPropertyDescriptor:h,getOwnPropertyNames:l,getOwnPropertySymbols:c,getPrototypeOf:d}=Object,p=globalThis,u=p.trustedTypes,$=u?u.emptyScript:"",g=p.reactiveElementPolyfillSupport,f=(t,e)=>t,v={toAttribute(t,e){switch(e){case Boolean:t=t?$:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let s=t;switch(e){case Boolean:s=null!==t;break;case Number:s=null===t?null:Number(t);break;case Object:case Array:try{s=JSON.parse(t)}catch(t){s=null}}return s}},_=(t,e)=>!n(t,e),y={attribute:!0,type:String,converter:v,reflect:!1,useDefault:!1,hasChanged:_};Symbol.metadata??=Symbol("metadata"),p.litPropertyMetadata??=new WeakMap;let m=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=y){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const s=Symbol(),i=this.getPropertyDescriptor(t,s,e);void 0!==i&&a(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){const{get:i,set:r}=h(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:i,set(e){const o=i?.call(this);r?.call(this,e),this.requestUpdate(t,o,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??y}static _$Ei(){if(this.hasOwnProperty(f("elementProperties")))return;const t=d(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(f("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(f("properties"))){const t=this.properties,e=[...l(t),...c(t)];for(const s of e)this.createProperty(s,t[s])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,s]of e)this.elementProperties.set(t,s)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const s=this._$Eu(t,e);void 0!==s&&this._$Eh.set(s,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const s=new Set(t.flat(1/0).reverse());for(const t of s)e.unshift(o(t))}else void 0!==t&&e.push(o(t));return e}static _$Eu(t,e){const s=e.attribute;return!1===s?void 0:"string"==typeof s?s:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const s=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((s,i)=>{if(e)s.adoptedStyleSheets=i.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const e of i){const i=document.createElement("style"),r=t.litNonce;void 0!==r&&i.setAttribute("nonce",r),i.textContent=e.cssText,s.appendChild(i)}})(s,this.constructor.elementStyles),s}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){const s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(void 0!==i&&!0===s.reflect){const r=(void 0!==s.converter?.toAttribute?s.converter:v).toAttribute(e,s.type);this._$Em=t,null==r?this.removeAttribute(i):this.setAttribute(i,r),this._$Em=null}}_$AK(t,e){const s=this.constructor,i=s._$Eh.get(t);if(void 0!==i&&this._$Em!==i){const t=s.getPropertyOptions(i),r="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:v;this._$Em=i;const o=r.fromAttribute(e,t.type);this[i]=o??this._$Ej?.get(i)??o,this._$Em=null}}requestUpdate(t,e,s,i=!1,r){if(void 0!==t){const o=this.constructor;if(!1===i&&(r=this[t]),s??=o.getPropertyOptions(t),!((s.hasChanged??_)(r,e)||s.useDefault&&s.reflect&&r===this._$Ej?.get(t)&&!this.hasAttribute(o._$Eu(t,s))))return;this.C(t,e,s)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:r},o){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,o??e??this[t]),!0!==r||void 0!==o)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),!0===i&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,s]of t){const{wrapped:t}=s,i=this[e];!0!==t||this._$AL.has(e)||void 0===i||this.C(e,void 0,s,i)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};m.elementStyles=[],m.shadowRootOptions={mode:"open"},m[f("elementProperties")]=new Map,m[f("finalized")]=new Map,g?.({ReactiveElement:m}),(p.reactiveElementVersions??=[]).push("2.1.2");const b=globalThis,A=t=>t,E=b.trustedTypes,x=E?E.createPolicy("lit-html",{createHTML:t=>t}):void 0,S="$lit$",w=`lit$${Math.random().toFixed(9).slice(2)}$`,P="?"+w,C=`<${P}>`,k=document,O=()=>k.createComment(""),U=t=>null===t||"object"!=typeof t&&"function"!=typeof t,D=Array.isArray,M="[ \t\n\f\r]",T=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,H=/-->/g,N=/>/g,R=RegExp(`>|${M}(?:([^\\s"'>=/]+)(${M}*=${M}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),j=/'/g,L=/"/g,z=/^(?:script|style|textarea|title)$/i,B=(t=>(e,...s)=>({_$litType$:t,strings:e,values:s}))(1),I=Symbol.for("lit-noChange"),q=Symbol.for("lit-nothing"),W=new WeakMap,V=k.createTreeWalker(k,129);function F(t,e){if(!D(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==x?x.createHTML(e):e}const J=(t,e)=>{const s=t.length-1,i=[];let r,o=2===e?"<svg>":3===e?"<math>":"",n=T;for(let e=0;e<s;e++){const s=t[e];let a,h,l=-1,c=0;for(;c<s.length&&(n.lastIndex=c,h=n.exec(s),null!==h);)c=n.lastIndex,n===T?"!--"===h[1]?n=H:void 0!==h[1]?n=N:void 0!==h[2]?(z.test(h[2])&&(r=RegExp("</"+h[2],"g")),n=R):void 0!==h[3]&&(n=R):n===R?">"===h[0]?(n=r??T,l=-1):void 0===h[1]?l=-2:(l=n.lastIndex-h[2].length,a=h[1],n=void 0===h[3]?R:'"'===h[3]?L:j):n===L||n===j?n=R:n===H||n===N?n=T:(n=R,r=void 0);const d=n===R&&t[e+1].startsWith("/>")?" ":"";o+=n===T?s+C:l>=0?(i.push(a),s.slice(0,l)+S+s.slice(l)+w+d):s+w+(-2===l?e:d)}return[F(t,o+(t[s]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),i]};class K{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let r=0,o=0;const n=t.length-1,a=this.parts,[h,l]=J(t,e);if(this.el=K.createElement(h,s),V.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(i=V.nextNode())&&a.length<n;){if(1===i.nodeType){if(i.hasAttributes())for(const t of i.getAttributeNames())if(t.endsWith(S)){const e=l[o++],s=i.getAttribute(t).split(w),n=/([.?@])?(.*)/.exec(e);a.push({type:1,index:r,name:n[2],strings:s,ctor:"."===n[1]?Y:"?"===n[1]?tt:"@"===n[1]?et:X}),i.removeAttribute(t)}else t.startsWith(w)&&(a.push({type:6,index:r}),i.removeAttribute(t));if(z.test(i.tagName)){const t=i.textContent.split(w),e=t.length-1;if(e>0){i.textContent=E?E.emptyScript:"";for(let s=0;s<e;s++)i.append(t[s],O()),V.nextNode(),a.push({type:2,index:++r});i.append(t[e],O())}}}else if(8===i.nodeType)if(i.data===P)a.push({type:2,index:r});else{let t=-1;for(;-1!==(t=i.data.indexOf(w,t+1));)a.push({type:7,index:r}),t+=w.length-1}r++}}static createElement(t,e){const s=k.createElement("template");return s.innerHTML=t,s}}function Z(t,e,s=t,i){if(e===I)return e;let r=void 0!==i?s._$Co?.[i]:s._$Cl;const o=U(e)?void 0:e._$litDirective$;return r?.constructor!==o&&(r?._$AO?.(!1),void 0===o?r=void 0:(r=new o(t),r._$AT(t,s,i)),void 0!==i?(s._$Co??=[])[i]=r:s._$Cl=r),void 0!==r&&(e=Z(t,r._$AS(t,e.values),r,i)),e}class G{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??k).importNode(e,!0);V.currentNode=i;let r=V.nextNode(),o=0,n=0,a=s[0];for(;void 0!==a;){if(o===a.index){let e;2===a.type?e=new Q(r,r.nextSibling,this,t):1===a.type?e=new a.ctor(r,a.name,a.strings,this,t):6===a.type&&(e=new st(r,this,t)),this._$AV.push(e),a=s[++n]}o!==a?.index&&(r=V.nextNode(),o++)}return V.currentNode=k,i}p(t){let e=0;for(const s of this._$AV)void 0!==s&&(void 0!==s.strings?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}}class Q{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=q,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=Z(this,t,e),U(t)?t===q||null==t||""===t?(this._$AH!==q&&this._$AR(),this._$AH=q):t!==this._$AH&&t!==I&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>D(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==q&&U(this._$AH)?this._$AA.nextSibling.data=t:this.T(k.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:s}=t,i="number"==typeof s?this._$AC(t):(void 0===s.el&&(s.el=K.createElement(F(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{const t=new G(i,this),s=t.u(this.options);t.p(e),this.T(s),this._$AH=t}}_$AC(t){let e=W.get(t.strings);return void 0===e&&W.set(t.strings,e=new K(t)),e}k(t){D(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let s,i=0;for(const r of t)i===e.length?e.push(s=new Q(this.O(O()),this.O(O()),this,this.options)):s=e[i],s._$AI(r),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const e=A(t).nextSibling;A(t).remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class X{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,r){this.type=1,this._$AH=q,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=r,s.length>2||""!==s[0]||""!==s[1]?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=q}_$AI(t,e=this,s,i){const r=this.strings;let o=!1;if(void 0===r)t=Z(this,t,e,0),o=!U(t)||t!==this._$AH&&t!==I,o&&(this._$AH=t);else{const i=t;let n,a;for(t=r[0],n=0;n<r.length-1;n++)a=Z(this,i[s+n],e,n),a===I&&(a=this._$AH[n]),o||=!U(a)||a!==this._$AH[n],a===q?t=q:t!==q&&(t+=(a??"")+r[n+1]),this._$AH[n]=a}o&&!i&&this.j(t)}j(t){t===q?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class Y extends X{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===q?void 0:t}}class tt extends X{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==q)}}class et extends X{constructor(t,e,s,i,r){super(t,e,s,i,r),this.type=5}_$AI(t,e=this){if((t=Z(this,t,e,0)??q)===I)return;const s=this._$AH,i=t===q&&s!==q||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,r=t!==q&&(s===q||i);i&&this.element.removeEventListener(this.name,this,s),r&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class st{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){Z(this,t)}}const it=b.litHtmlPolyfillSupport;it?.(K,Q),(b.litHtmlVersions??=[]).push("3.3.2");const rt=globalThis;class ot extends m{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,s)=>{const i=s?.renderBefore??e;let r=i._$litPart$;if(void 0===r){const t=s?.renderBefore??null;i._$litPart$=r=new Q(e.insertBefore(O(),t),t,void 0,s??{})}return r._$AI(t),r})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return I}}ot._$litElement$=!0,ot.finalized=!0,rt.litElementHydrateSupport?.({LitElement:ot});const nt=rt.litElementPolyfillSupport;nt?.({LitElement:ot}),(rt.litElementVersions??=[]).push("4.2.2");class at extends ot{constructor(){super(...arguments),Object.defineProperty(this,"_hass",{enumerable:!0,configurable:!0,writable:!0,value:void 0}),Object.defineProperty(this,"devices",{enumerable:!0,configurable:!0,writable:!0,value:[]}),Object.defineProperty(this,"loading",{enumerable:!0,configurable:!0,writable:!0,value:!1}),Object.defineProperty(this,"message",{enumerable:!0,configurable:!0,writable:!0,value:""}),Object.defineProperty(this,"error",{enumerable:!0,configurable:!0,writable:!0,value:""}),Object.defineProperty(this,"serviceDrafts",{enumerable:!0,configurable:!0,writable:!0,value:{}}),Object.defineProperty(this,"savingByEntry",{enumerable:!0,configurable:!0,writable:!0,value:{}})}get hass(){return this._hass}set hass(t){this._hass=t,t&&0===this.devices.length&&!this.loading&&this.runAsync(()=>this.refreshDevices()),this.requestUpdate()}render(){return B`
      <h1>Perimeter Control</h1>
      <p class="sub">Manage installed devices and update enabled service options.</p>
      <div class="toolbar">
        <button @click=${()=>this.runAsync(()=>this.refreshDevices())}>Refresh Devices</button>
      </div>

      ${this.message?B`<div class="msg ok">${this.message}</div>`:q}
      ${this.error?B`<div class="msg err">${this.error}</div>`:q}
      ${this.loading?B`<p class="loading">Loading devices...</p>`:q}

      ${this.loading||0!==this.devices.length?q:B`<p>No devices found. Add a Perimeter Control integration entry first.</p>`}

      <div class="grid">
        ${this.devices.map(t=>this.renderDeviceCard(t))}
      </div>
    `}renderDeviceCard(t){const e=Array.isArray(t.available_services)?t.available_services:[],s=new Set(this.serviceDrafts[t.entry_id]||t.services||[]),i=!!this.savingByEntry[t.entry_id];return B`
      <div class="card">
        <p class="title">${t.title||"Perimeter Device"}</p>
        <p class="meta">Host: ${t.host||"unknown"}</p>
        <p class="meta">
          Dashboard: ${t.dashboard_active?"online":"offline"} |
          Supervisor: ${t.supervisor_active?"online":"offline"}
        </p>

        <div class="services">
          <strong>Enabled services</strong>
          ${e.length?e.map(e=>B`
                  <label class="svc">
                    <input
                      type="checkbox"
                      .checked=${s.has(e)}
                      @change=${s=>this.toggleService(t.entry_id,e,s.currentTarget.checked)}
                    />
                    ${e}
                  </label>
                `):B`<p class="meta">No service options available.</p>`}
        </div>

        <div class="card-actions">
          <button
            class="primary"
            ?disabled=${i}
            @click=${()=>this.runAsync(()=>this.saveServices(t.entry_id))}
          >
            ${i?"Saving...":"Save Services"}
          </button>
          <button
            ?disabled=${!!t.deploy_in_progress}
            @click=${()=>this.runAsync(()=>this.deployDevice(t.entry_id))}
          >
            ${t.deploy_in_progress?"Deploying...":"Deploy Device"}
          </button>
        </div>

        ${this.renderDashboardLinks(t)}
      </div>
    `}renderDashboardLinks(t){const e=t.dashboard_urls??{},s=Object.entries(e).filter(([,t])=>!!t);return s.length?B`
      <div class="dashboards">
        <strong>Dashboards</strong><br />
        ${s.map(([t,e])=>B`<a class="dash-link" href=${e} target="_blank" rel="noopener noreferrer"
              >${t}</a
            >`)}
      </div>
    `:q}async api(t,e,s){if(!this._hass)throw new Error("Home Assistant is not available");return this._hass.callApi(t,e,s)}isAbortLikeError(t){if(!t||"object"!=typeof t)return!1;const e=t,s=String(e.name??""),i=String(e.message??"");return"AbortError"===s||i.includes("Transition was skipped")}runAsync(t){Promise.resolve().then(t).catch(t=>{this.isAbortLikeError(t)||(this.error=`Unexpected error: ${this.toErrorMessage(t)}`,this.message="")})}toErrorMessage(t){return t instanceof Error?t.message:String(t)}async refreshDevices(){this.loading=!0,this.error="",this.message="";try{const t=await this.api("GET","perimeter_control/devices"),e=Array.isArray(t)?t:[];this.devices=e;const s={};for(const t of e)s[t.entry_id]=[...t.services||[]];this.serviceDrafts=s}catch(t){if(this.isAbortLikeError(t))return;this.error=`Failed to load devices: ${this.toErrorMessage(t)}`}finally{this.loading=!1}}toggleService(t,e,s){const i=new Set(this.serviceDrafts[t]||[]);s?i.add(e):i.delete(e),this.serviceDrafts={...this.serviceDrafts,[t]:Array.from(i)}}async saveServices(t){const e=[...this.serviceDrafts[t]||[]];if(!e.length)return this.error="Select at least one service before saving.",void(this.message="");this.savingByEntry={...this.savingByEntry,[t]:!0},this.error="",this.message="";try{await this.api("POST",`perimeter_control/${t}/services`,{services:e}),this.message="Service options updated successfully.",await this.refreshDevices()}catch(t){if(this.isAbortLikeError(t))return;this.error=`Failed to save service options: ${this.toErrorMessage(t)}`}finally{this.savingByEntry={...this.savingByEntry,[t]:!1}}}async deployDevice(t){this.error="",this.message="";try{await this.api("POST",`perimeter_control/${t}/deploy`,{}),this.message="Deploy queued.",await this.refreshDevices()}catch(t){if(this.isAbortLikeError(t))return;this.error=`Failed to queue deploy: ${this.toErrorMessage(t)}`}}}Object.defineProperty(at,"properties",{enumerable:!0,configurable:!0,writable:!0,value:{hass:{attribute:!1},devices:{state:!0},loading:{state:!0},message:{state:!0},error:{state:!0},serviceDrafts:{state:!0},savingByEntry:{state:!0}}}),Object.defineProperty(at,"styles",{enumerable:!0,configurable:!0,writable:!0,value:((t,...e)=>{const i=1===t.length?t[0]:e.reduce((e,s,i)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(s)+t[i+1],t[0]);return new r(i,t,s)})`
    :host {
      display: block;
      padding: 16px;
      max-width: 1100px;
      margin: 0 auto;
      box-sizing: border-box;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 24px;
      font-weight: 600;
    }

    .sub {
      margin: 0 0 16px;
      color: var(--secondary-text-color);
    }

    .toolbar {
      margin-bottom: 16px;
    }

    button {
      border: 1px solid var(--divider-color);
      border-radius: 6px;
      background: var(--card-background-color);
      color: var(--primary-text-color);
      padding: 8px 12px;
      cursor: pointer;
    }

    button.primary {
      background: var(--primary-color);
      border-color: var(--primary-color);
      color: #fff;
    }

    button:disabled {
      opacity: 0.6;
      cursor: default;
    }

    .msg {
      margin: 8px 0 16px;
      padding: 8px 10px;
      border-radius: 6px;
      font-size: 14px;
    }

    .ok {
      background: #e8f5e9;
      color: #1b5e20;
      border: 1px solid #a5d6a7;
    }

    .err {
      background: #ffebee;
      color: #b71c1c;
      border: 1px solid #ef9a9a;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 14px;
    }

    .card {
      border: 1px solid var(--divider-color);
      border-radius: 10px;
      padding: 14px;
      background: var(--card-background-color);
    }

    .title {
      font-weight: 600;
      margin: 0 0 4px;
    }

    .meta {
      margin: 0 0 8px;
      color: var(--secondary-text-color);
      font-size: 13px;
    }

    .services {
      border-top: 1px dashed var(--divider-color);
      margin-top: 10px;
      padding-top: 10px;
    }

    .svc {
      display: block;
      margin: 4px 0;
      font-size: 14px;
    }

    .card-actions {
      margin-top: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .loading {
      opacity: 0.8;
    }

    .dashboards {
      border-top: 1px dashed var(--divider-color);
      margin-top: 10px;
      padding-top: 10px;
    }

    .dash-link {
      display: inline-block;
      margin: 3px 6px 3px 0;
      font-size: 13px;
      color: var(--primary-color);
      text-decoration: none;
      border: 1px solid var(--primary-color);
      border-radius: 4px;
      padding: 2px 8px;
    }

    .dash-link:hover {
      opacity: 0.8;
    }
  `}),customElements.get("perimeter-control-panel")||customElements.define("perimeter-control-panel",at);

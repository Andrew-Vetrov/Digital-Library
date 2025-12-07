import './view.js'
import { createTOCView } from './tree.js'
import { createMenu } from './menu.js'
import { Overlayer } from './overlayer.js'

const getCSS = ({ spacing, justify, hyphenate }) => `
    @namespace epub "http://www.idpf.org/2007/ops";
    html {
        color-scheme: light dark;
    }
    /* https://github.com/whatwg/html/issues/5426 */
    @media (prefers-color-scheme: dark) {
        a:link {
            color: lightblue;
        }
    }
    p, li, blockquote, dd {
        line-height: ${spacing};
        text-align: ${justify ? 'justify' : 'start'};
        -webkit-hyphens: ${hyphenate ? 'auto' : 'manual'};
        hyphens: ${hyphenate ? 'auto' : 'manual'};
        -webkit-hyphenate-limit-before: 3;
        -webkit-hyphenate-limit-after: 2;
        -webkit-hyphenate-limit-lines: 2;
        hanging-punctuation: allow-end last;
        widows: 2;
    }
    /* prevent the above from overriding the align attribute */
    [align="left"] { text-align: left; }
    [align="right"] { text-align: right; }
    [align="center"] { text-align: center; }
    [align="justify"] { text-align: justify; }

    pre {
        white-space: pre-wrap !important;
    }
    aside[epub|type~="endnote"],
    aside[epub|type~="footnote"],
    aside[epub|type~="note"],
    aside[epub|type~="rearnote"] {
        display: none;
    }
`

const $ = document.querySelector.bind(document)

const locales = 'en'
const percentFormat = new Intl.NumberFormat(locales, { style: 'percent' })
const listFormat = new Intl.ListFormat(locales, { style: 'short', type: 'conjunction' })

const formatLanguageMap = x => {
    if (!x) return ''
    if (typeof x === 'string') return x
    const keys = Object.keys(x)
    return x[keys[0]]
}

const formatOneContributor = contributor => typeof contributor === 'string'
    ? contributor : formatLanguageMap(contributor?.name)

const formatContributor = contributor => Array.isArray(contributor)
    ? listFormat.format(contributor.map(formatOneContributor))
    : formatOneContributor(contributor)

class Reader {
    #bookId = null
    #lastSaveTime = 0
    #saveTimeout = null
    #isSaving = false
    #minSaveInterval = 2000
    #tocView
    style = {
        spacing: 1.4,
        justify: true,
        hyphenate: true,
    }
    annotations = new Map()
    annotationsByValue = new Map()
    closeSideBar() {
        $('#dimming-overlay').classList.remove('show')
        $('#side-bar').classList.remove('show')
    }
    constructor() {
        $('#side-bar-button').addEventListener('click', () => {
            $('#dimming-overlay').classList.add('show')
            $('#side-bar').classList.add('show')
        })
        $('#dimming-overlay').addEventListener('click', () => this.closeSideBar())
        this.#bookId = this.#extractBookId()

        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.saveCurrentPosition()
            }
        })
        
    }

    #extractBookId() {
        // Вариант 1: Из data-атрибута
        const appElement = document.getElementById('app')
        if (appElement?.dataset.bookId) {
            return parseInt(appElement.dataset.bookId)
        }
        
        
        console.error("ERROR PARSING BOOKID")
        return null // Для локальных файлов без book_id
    }

    async #restoreFromSavedPosition(savedData) {
    if (!savedData?.loc) return
    
    try {
        if (this.view.convertLocToPosition) {
            const position = this.view.convertLocToPosition(
                savedData.loc,
                savedData.location_total
            )
            
            if (position.index !== undefined) {
                await this.view.goTo(position)
                console.log(`Restored to Loc ${savedData.loc}, section ${position.index}`)
                return
            }
        }
        
        // Fallback: используем fraction если есть
        if (savedData.fraction !== undefined) {
            await this.view.goToFraction(savedData.fraction)
            console.log(`Restored to fraction ${savedData.fraction} (Loc ${savedData.loc})`)
        }
        
    } catch (e) {
        console.error('Failed to restore:', e)
    }
}
    
    
    
    #onRelocate({ detail }) {
        const { fraction, location, tocItem, pageItem } = detail
        if (location?.current !== undefined && this.#bookId) {
            // Отменяем предыдущий таймер
            if (this.#saveTimeout) {
                clearTimeout(this.#saveTimeout)
            }
            
            // Сохраняем через 1 секунду после последнего изменения
            this.#saveTimeout = setTimeout(() => {
                this.#saveLoc(location.current)
            }, 1000)
        }

        const percent = percentFormat.format(fraction)
        const loc = pageItem
            ? `Page ${pageItem.label}`
            : `Loc ${location.current}`
        const slider = $('#progress-slider')
        slider.style.visibility = 'visible'
        slider.value = fraction
        slider.title = `${percent} · ${loc}`
        if (tocItem?.href) this.#tocView?.setCurrentHref?.(tocItem.href)
    }
    
    #schedulePositionSave(positionData) {
        // Отменяем предыдущий таймер
        if (this.#saveTimeout) {
            clearTimeout(this.#saveTimeout)
        }
        
        // Дебаунс: сохраняем через 1 секунду после последнего изменения
        this.#saveTimeout = setTimeout(() => {
            this.#savePositionToServer(positionData)
        }, 1000)
    }
    
    async #savePositionToServer(positionData) {
        if (!this.#bookId || this.#isSaving) return
        
        // Проверяем частоту сохранений
        const now = Date.now()
        if (now - this.#lastSaveTime < this.#minSaveInterval) {
            return // Слишком часто
        }
        
        this.#isSaving = true
        
        try {
            const data = {
                loc: positionData.loc,
                location_current: positionData.loc,
                location_total: positionData.location_total,
                fraction: positionData.fraction,
                cfi: positionData.cfi,
                section_index: positionData.section_index,
                saved_at: new Date().toISOString(),
                reason: positionData.reason || 'auto_save'
            }
            
            // Удаляем пустые поля
            Object.keys(data).forEach(key => {
                if (data[key] === undefined || data[key] === null) {
                    delete data[key]
                }
            })
            
            // Используем sendBeacon для надежного сохранения
            const blob = new Blob([JSON.stringify(data)], { type: 'application/json' })
            const success = navigator.sendBeacon?.(
                `http://localhost:3000/reading_progress/${this.#bookId}`,
                blob
            )
            
            if (!success) {
                // Fallback на обычный fetch
                await fetch(`http://localhost:3000/reading_progress/${this.#bookId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                    keepalive: true
                })
            }
            
            this.#lastSaveTime = Date.now()
            console.log(`Position saved: Loc ${data.loc}`)
            
        } catch (e) {
            console.error('Failed to save position:', e)
        
        } finally {
            this.#isSaving = false
        }
    }
    
    #saveToLocalStorage(positionData) {
        try {
            const key = `book_position_${this.#bookId}`
            localStorage.setItem(key, JSON.stringify({
                ...positionData,
                saved_at: new Date().toISOString(),
                is_backup: true
            }))
        } catch (e) {
            console.error('Failed to save to localStorage:', e)
        }
    }
    
    #savePosition(reason) {
        if (!this.view?.lastLocation || !this.#bookId) return
        
        const position = this.view.lastLocation
        
        this.#savePositionToServer({
            loc: position.location?.current,
            location_total: position.location?.total,
            fraction: position.fraction,
            cfi: position.cfi,
            section_index: position.section?.current,
            reason: reason
        })
    }

    async open(file) {
        let savedLoc = null
        if (this.#bookId) {
            try {
                const response = await fetch(`http://localhost:3000/reading_progress/${this.#bookId}`)
                if (response.ok) {
                    const data = await response.json()
                    if (data.loc !== null && data.loc !== undefined) {
                        savedLoc = data.loc
                        console.log(`Loaded saved Loc: ${savedLoc}`)
                    }
                }
            } catch (e) {
                console.error('Failed to load saved position:', e)
            }
        }
        this.view = document.createElement('diglib-view')
        document.body.append(this.view)
        await this.view.open(file)
        this.view.addEventListener('load', this.#onLoad.bind(this))
        this.view.addEventListener('relocate', this.#onRelocate.bind(this))

        const { book } = this.view
        book.transformTarget?.addEventListener('data', ({ detail }) => {
            detail.data = Promise.resolve(detail.data).catch(e => {
                console.error(new Error(`Failed to load ${detail.name}`, { cause: e }))
                return ''
            })
        })
        this.view.renderer.setStyles?.(getCSS(this.style))
        this.view.renderer.next()

        $('#header-bar').style.visibility = 'visible'
        $('#nav-bar').style.visibility = 'visible'
        $('#left-button').addEventListener('click', () => this.view.goLeft())
        $('#right-button').addEventListener('click', () => this.view.goRight())

        const slider = $('#progress-slider')
        slider.dir = book.dir
        slider.addEventListener('input', e =>
            this.view.goToFraction(parseFloat(e.target.value)))
        for (const fraction of this.view.getSectionFractions()) {
            const option = document.createElement('option')
            option.value = fraction
            $('#tick-marks').append(option)
        }

        document.addEventListener('keydown', this.#handleKeydown.bind(this))

        const title = formatLanguageMap(book.metadata?.title) || 'Untitled Book'
        document.title = title
        $('#side-bar-title').innerText = title
        $('#side-bar-author').innerText = formatContributor(book.metadata?.author)
        Promise.resolve(book.getCover?.())?.then(blob =>
            blob ? $('#side-bar-cover').src = URL.createObjectURL(blob) : null)

        const toc = book.toc
        if (toc) {
            this.#tocView = createTOCView(toc, href => {
                this.view.goTo(href).catch(e => console.error(e))
                this.closeSideBar()
            })
            $('#toc-view').append(this.#tocView.element)
        }

        // load and show highlights embedded in the file by Calibre
        const bookmarks = await book.getCalibreBookmarks?.()
        if (bookmarks) {
            const { fromCalibreHighlight } = await import('./epubcfi.js')
            for (const obj of bookmarks) {
                if (obj.type === 'highlight') {
                    const value = fromCalibreHighlight(obj)
                    const color = obj.style.which
                    const note = obj.notes
                    const annotation = { value, color, note }
                    const list = this.annotations.get(obj.spine_index)
                    if (list) list.push(annotation)
                    else this.annotations.set(obj.spine_index, [annotation])
                    this.annotationsByValue.set(value, annotation)
                }
            }
            this.view.addEventListener('create-overlay', e => {
                const { index } = e.detail
                const list = this.annotations.get(index)
                if (list) for (const annotation of list)
                    this.view.addAnnotation(annotation)
            })
            this.view.addEventListener('draw-annotation', e => {
                const { draw, annotation } = e.detail
                const { color } = annotation
                draw(Overlayer.highlight, { color })
            })
            this.view.addEventListener('show-annotation', e => {
                const annotation = this.annotationsByValue.get(e.detail.value)
                if (annotation.note) alert(annotation.note)
            })
        }

         if (savedLoc !== null) {
            // Ждем немного пока книга загрузится
            setTimeout(() => {
                this.#restorePosition(savedLoc)
            }, 500)
        } else {
            this.view.renderer.next()
        }
    }

    async #restorePosition(locNumber) {
        try {
            // Преобразуем Loc во fraction для навигации
            const totalLocs = this.view.lastLocation?.location?.total
            
            if (totalLocs && locNumber < totalLocs) {
                const fraction = locNumber / totalLocs
                await this.view.goToFraction(fraction)
                console.log(`Restored to Loc ${locNumber}`)
                
                // Можно показать уведомление
            } else {
                // Если не можем вычислить, начинаем с начала
                await this.view.goToTextStart()
            }
        } catch (e) {
            console.error('Failed to restore position:', e)
        }
    }

    #handleKeydown(event) {
        const k = event.key
        if (k === 'ArrowLeft' || k === 'h') this.view.goLeft()
        else if(k === 'ArrowRight' || k === 'l') this.view.goRight()
    }
    #onLoad({ detail: { doc } }) {
        doc.addEventListener('keydown', this.#handleKeydown.bind(this))
    }
    

     async #saveLoc(locNumber) {
        if (!this.#bookId) return
        
        try {
            const response = await fetch(`http://localhost:3000/reading_progress/${this.#bookId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ loc: locNumber })
            })
            
            if (response.ok) {
                console.log(`Loc ${locNumber} saved successfully`)
            } else {
                console.error(`Failed to save Loc ${locNumber}: ${response.status}`)
            }
        } catch (e) {
            console.error('Error saving Loc:', e)
        }
    }

    saveCurrentPosition() {
        if (!this.view?.lastLocation?.location?.current || !this.#bookId) return
        this.#saveLoc(this.view.lastLocation.location.current)
    }
}

const open = async file => {
    const reader = new Reader()
    globalThis.reader = reader
    await reader.open(file)
}



const bookUrl = document.getElementById("app").dataset.bookUrl;
if (bookUrl) open(bookUrl).catch(e => console.error(e))
else dropTarget.style.visibility = 'visible'
/** @odoo-module **/

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { patch } from "@web/core/utils/patch";

patch(Chatter.prototype, {
    /**
     * @param {string} data deprecated, passing thread is enough
     * @param {import("models").Thread} thread
     */
    onUploaded(data, { thread } = {}) {
        if (thread?.model !== "project.task") {
            return super.onUploaded(...arguments);
        }

        const threadLocalId = thread.localId;
        if (!this.uploadHandlers.has(threadLocalId)) {
            const self = this;
            this.uploadHandlers.set(threadLocalId, async function handleUpload(uploadData) {
                try {
                    if (uploadData.file instanceof File) {
                        await self.attachmentUploader.uploadFile(uploadData.file, { thread });
                    } else {
                        await self.attachmentUploader.uploadData(uploadData, { thread });
                    }
                    if (!thread.eq(self.state.thread)) {
                        return;
                    }
                    if (self.props.hasParentReloadOnAttachmentsChanged) {
                        self.reloadParentView();
                    }
                    self.state.isAttachmentBoxOpened = true;
                    if (self.rootRef.el) {
                        self.rootRef.el.scrollTop = 0;
                    }
                    self.state.thread.scrollTop = "bottom";
                } finally {
                    self.uploadHandlers.delete(threadLocalId);
                }
            });
        }
        return this.uploadHandlers.get(threadLocalId);
    },
});

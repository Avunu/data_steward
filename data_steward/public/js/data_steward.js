// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

// Global data_steward object for capability checking
window.data_steward = {
	/**
	 * Check if a Data Steward capability is enabled (for UI decisions)
	 * @param {DataStewardCapability} capability - The capability to check
	 * @returns {Promise<boolean>} - Promise that resolves to true if enabled, false otherwise
	 */
	check_capability: function (capability) {
		return new Promise((resolve) => {
			frappe.call({
				method: "data_steward.api.check_capability",
				args: {
					capability: capability,
				},
				callback: function (r) {
					resolve(Boolean(r.message));
				},
				error: function () {
					resolve(false);
				},
			});
		});
	},
};

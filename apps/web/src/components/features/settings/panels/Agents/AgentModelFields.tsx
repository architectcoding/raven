import { useFormContext, useWatch } from "react-hook-form"
import { useFrappeGetCall } from "frappe-react-sdk"
import { useRavenSettings } from "@hooks/fetchers/useRavenSettings"
import {
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
    FormRequiredIndicator,
} from "@components/ui/form"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@components/ui/select"
import type { RavenBot } from "@raven/types/RavenBot/RavenBot"
import _ from "@lib/translate"

/** Model provider select — only enabled providers; the no-provider state (full-width alert) is handled by AgentAITab. */
const ModelProviderSelector = () => {
    const { control } = useFormContext<RavenBot>()
    const { ravenSettings } = useRavenSettings()
    const isAiBot = useWatch({ control, name: "is_ai_bot" })

    if (!isAiBot) return null

    const hasOpenAI = ravenSettings?.enable_openai_services === 1
    const hasAnthropic = ravenSettings?.enable_anthropic_services === 1
    const hasGemini = ravenSettings?.enable_gemini_services === 1
    const hasDeepSeek = ravenSettings?.enable_deepseek_services === 1
    const hasLocalLLM = ravenSettings?.enable_local_llm === 1

    if (!hasOpenAI && !hasAnthropic && !hasGemini && !hasDeepSeek && !hasLocalLLM) return null

    const fallbackProvider = hasOpenAI
        ? "OpenAI"
        : hasAnthropic ? "Anthropic" : hasGemini ? "Gemini" : hasDeepSeek ? "DeepSeek" : "Local LLM"

    return (
        <FormField
            control={control}
            name="model_provider"
            rules={{ required: isAiBot ? _("Please select a model provider") : false }}
            defaultValue={fallbackProvider}
            render={({ field }) => (
                <FormItem>
                    <FormLabel>
                        {_("Model Provider")}
                        <FormRequiredIndicator />
                    </FormLabel>
                    <FormControl>
                        <Select value={field.value || fallbackProvider} onValueChange={field.onChange}>
                            <FormControl>
                                <SelectTrigger className="w-full">
                                    <SelectValue />
                                </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                                {hasOpenAI && <SelectItem value="OpenAI">{_("OpenAI")}</SelectItem>}
                                {hasAnthropic && <SelectItem value="Anthropic">{_("Anthropic (Claude)")}</SelectItem>}
                                {hasGemini && <SelectItem value="Gemini">{_("Google Gemini")}</SelectItem>}
                                {hasDeepSeek && <SelectItem value="DeepSeek">{_("DeepSeek")}</SelectItem>}
                                {hasLocalLLM && <SelectItem value="Local LLM">{_("Local LLM")}</SelectItem>}
                            </SelectContent>
                        </Select>
                    </FormControl>
                    <FormMessage />
                </FormItem>
            )}
        />
    )
}

/** Model select — OpenAI models from the Assistants API, local models from the LLM server. */
const ModelSelector = () => {
    const { control } = useFormContext<RavenBot>()
    const { ravenSettings } = useRavenSettings()
    const isAiBot = useWatch({ control, name: "is_ai_bot" })
    const modelProvider = useWatch({ control, name: "model_provider" })

    const { data: openaiModels } = useFrappeGetCall<{ message: string[] }>(
        "raven.api.ai_features.get_openai_available_models",
        undefined,
        isAiBot && (modelProvider === "OpenAI" || !modelProvider) ? undefined : null,
        { revalidateOnFocus: false, revalidateIfStale: false }
    )

    // Asked of the API so a newly released Claude model is selectable without a new Raven build.
    const { data: anthropicModels } = useFrappeGetCall<{ message: string[] }>(
        "raven.api.ai_features.get_anthropic_available_models",
        undefined,
        isAiBot && modelProvider === "Anthropic" ? undefined : null,
        { revalidateOnFocus: false, revalidateIfStale: false }
    )

    const { data: geminiModels } = useFrappeGetCall<{ message: string[] }>(
        "raven.api.ai_features.get_gemini_available_models",
        undefined,
        isAiBot && modelProvider === "Gemini" ? undefined : null,
        { revalidateOnFocus: false, revalidateIfStale: false }
    )

    const { data: deepseekModels } = useFrappeGetCall<{ message: string[] }>(
        "raven.api.ai_features.get_deepseek_available_models",
        undefined,
        isAiBot && modelProvider === "DeepSeek" ? undefined : null,
        { revalidateOnFocus: false, revalidateIfStale: false }
    )

    const { data: localModelData } = useFrappeGetCall<{ message: { success: boolean; models?: { id: string }[] } }>(
        "raven.api.ai_features.test_llm_configuration",
        { provider: "Local LLM", api_url: ravenSettings?.local_llm_api_url, local_llm_provider: ravenSettings?.local_llm_provider },
        modelProvider === "Local LLM" && ravenSettings?.local_llm_api_url ? undefined : null,
        { revalidateOnFocus: false, revalidateIfStale: false }
    )

    const localModels = localModelData?.message.models?.map((model) => model.id) || []

    if (!isAiBot) return null

    const models: string[] = modelProvider === "Local LLM"
        ? localModels
        : modelProvider === "Anthropic"
            ? anthropicModels?.message || []
            : modelProvider === "Gemini"
                ? geminiModels?.message || []
                : modelProvider === "DeepSeek"
                    ? deepseekModels?.message || []
                    : openaiModels?.message || []
    const defaultModel = modelProvider === "Local LLM"
        ? localModels[0] || ""
        : modelProvider === "Anthropic"
            ? "claude-opus-5"
            : modelProvider === "Gemini"
                ? "gemini-flash-latest"
                : modelProvider === "DeepSeek"
                    ? "deepseek-chat"
                    : "gpt-4o"
    const validModels = models.filter((model) => model && model.trim() !== "")

    return (
        <FormField
            control={control}
            name="model"
            rules={{ required: isAiBot ? _("Please select a model") : false }}
            defaultValue={defaultModel}
            render={({ field }) => (
                <FormItem>
                    <FormLabel>
                        {_("Model")}
                        <FormRequiredIndicator />
                    </FormLabel>
                    <FormControl>
                        <Select value={field.value || defaultModel} onValueChange={field.onChange}>
                            <FormControl>
                                <SelectTrigger className="w-full">
                                    <SelectValue />
                                </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                                {validModels.length > 0 ? (
                                    validModels.map((model) => (
                                        <SelectItem key={model} value={model}>{model}</SelectItem>
                                    ))
                                ) : modelProvider === "Local LLM" ? (
                                    <SelectItem value="no-models" disabled>{_("No models available")}</SelectItem>
                                ) : (
                                    <SelectItem value={defaultModel}>{defaultModel}</SelectItem>
                                )}
                            </SelectContent>
                        </Select>
                    </FormControl>
                    <FormDescription>
                        {modelProvider === "Gemini"
                            ? _("Models are listed live from Google. Flash is the cheapest and is usually enough for document lookups; Pro is stronger on multi-step reasoning.")
                            : modelProvider === "Local LLM"
                            ? _("Select a model available on your local LLM server.")
                            : _("The model should be compatible with the OpenAI Assistants API. We recommend using models in the GPT-4 family for best results.")}
                    </FormDescription>
                    <FormMessage />
                </FormItem>
            )}
        />
    )
}

/** Reasoning effort select — OpenAI o-series models and every Claude model; defaults to medium. */
const ReasoningEffortSelector = () => {
    const { control } = useFormContext<RavenBot>()
    const model = useWatch({ control, name: "model" })
    const isAiBot = useWatch({ control, name: "is_ai_bot" })
    const isAnthropicProvider = useWatch({ control, name: "model_provider" }) === "Anthropic"

    // OpenAI only exposes effort on its o-series; every Claude model takes it.
    if (!isAiBot || !model || !(isAnthropicProvider || model.startsWith("o"))) return null

    return (
        <FormField
            control={control}
            name="reasoning_effort"
            rules={{ required: true }}
            defaultValue="medium"
            render={({ field }) => (
                <FormItem>
                    <FormLabel>
                        {_("Reasoning Effort")}
                        <FormRequiredIndicator />
                    </FormLabel>
                    <FormControl>
                        <Select value={field.value || "medium"} onValueChange={field.onChange}>
                            <FormControl>
                                <SelectTrigger className="w-full">
                                    <SelectValue />
                                </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                                <SelectItem value="low">{_("Low")}</SelectItem>
                                <SelectItem value="medium">{_("Medium")}</SelectItem>
                                <SelectItem value="high">{_("High")}</SelectItem>
                                {isAnthropicProvider && <SelectItem value="xhigh">{_("Extra High")}</SelectItem>}
                                {isAnthropicProvider && <SelectItem value="max">{_("Max")}</SelectItem>}
                            </SelectContent>
                        </Select>
                    </FormControl>
                    <FormDescription>
                        {isAnthropicProvider
                            ? _("How hard Claude thinks before answering. 'High' suits most work; 'Extra High' is the better default for tool-heavy agents.")
                            : _("The reasoning effort will be used to determine the depth of the reasoning process. This is only applicable for OpenAI's o-series models.")}
                    </FormDescription>
                    <FormMessage />
                </FormItem>
            )}
        />
    )
}

export { ModelProviderSelector, ModelSelector, ReasoningEffortSelector }
